# -*- coding: utf-'8' "-*-"
import time
from datetime import datetime, timedelta
from odoo import api, models, fields
from odoo.tools import float_round, DEFAULT_SERVER_DATE_FORMAT
from odoo.tools.float_utils import float_compare, float_repr
from odoo.tools.safe_eval import safe_eval
from odoo.tools.translate import _
from odoo.addons.payment.models.payment_acquirer import ValidationError
import logging
_logger = logging.getLogger(__name__)

#try:
from .pyflow.client import Client
#except:
#    _logger.warning("No se puede cargar Flow")


class PaymentAcquirerFlow(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(
            selection_add=[('flow', 'Flow')]
        )
    flow_api_key = fields.Char(
            string="Api Key",
        )
    flow_private_key = fields.Char(
            string="Secret Key",
        )
    flow_payment_method = fields.Selection(
        [
            ('1', 'Webpay'),
            ('2', 'Servipag'),
            ('3', 'Multicaja'),
            ('5', 'Onepay'),
            ('8', 'Cryptocompra'),
            ('9', 'Todos los medios'),
        ],
        required=True,
        default='1',
    )

     
    def _get_feature_support(self):
        res = super(PaymentAcquirerFlow, self)._get_feature_support()
        res['fees'].append('flow')
        return res

     
    def flow_compute_fees(self, amount, currency_id, country_id):
        """ Compute paypal fees.

            :param float amount: the amount to pay
            :param integer country_id: an ID of a res.country, or None. This is
                                       the customer's country, to be compared to
                                       the acquirer company country.
            :return float fees: computed fees
        """
        if not self.fees_active:
            return 0.0
        country = self.env['res.country'].browse(country_id)
        if country and self.company_id.country_id.id == country.id:
            percentage = self.fees_dom_var
            fixed = self.fees_dom_fixed
        else:
            percentage = self.fees_int_var
            fixed = self.fees_int_fixed
        factor = (percentage / 100.0) + (0.19 * (percentage /100.0))
        fees = ((amount + fixed) / (1 - factor))
        return fees

    @api.model
    def _get_flow_urls(self, state):
        base_url = self.env['ir.config_parameter'].sudo().get_param(
                    'web.base.url')
        if state == 'prod':
            return {
                'flow_form_url': base_url + '/payment/flow/redirect',
                'flow_url': "https://www.flow.cl/api",
            }
        else:
            return {
                'flow_form_url': base_url + '/payment/flow/redirect',
                'flow_url': "https://sandbox.flow.cl/api",
            }

     
    def flow_form_generate_values(self, values):
        #banks = self.flow_get_banks()#@TODO mostrar listados de bancos
        #_logger.warning("banks %s" %banks)
        values.update({
            'acquirer_id': self.id,
            'commerceOrder': values['reference'],
            'subject': '%s: %s' % (self.company_id.name, values['reference']),
            'amount': values['amount'],
            'email': values['partner_email'],
            'paymentMethod': self.flow_payment_method,
            'fees': values.get('fees', 0),
        })
        return values

     
    def flow_get_form_action_url(self):
        return self._get_flow_urls(self.state)['flow_form_url']

    def flow_get_client(self,):
        return Client(
                self.flow_api_key,
                self.flow_private_key,
                self._get_flow_urls(self.state)['flow_url'],
                (self.state == 'test'),
            )

    def flow_get_banks(self):
        client = self.flow_get_client()
        return client.banks.get() 

    def flow_initTransaction(self, post):
        base_url = self.env['ir.config_parameter'].sudo().get_param(
                    'web.base.url')
        tx = self.env['payment.transaction'].search([
                    ('reference', '=', post.get('transaction_id'))
                    ])
        del(post['acquirer_id'])
        del(post['transaction_id'])
        amount = (float(post['amount'])) # + float(post['fees'])
        currency = self.env['res.currency'].search([
            ('name', '=', post.get('currency', 'CLP')),
        ])
        if self.force_currency and currency != self.force_currency_id:
            post['amount'] = lambda price: currency.compute(
                                amount,
                                self.force_currency_id)
            currency = self.force_currency

        if amount < 350:
            raise ValidationError("Monto total no debe ser menor a $350")
        post.update({
                    'paymentMethod': str(post.get('paymentMethod')),
                    'urlConfirmation': base_url + '/payment/flow/notify/%s' % str(self.id),
                    'urlReturn': base_url + '/payment/flow/return/%s' % str(tx.id),
                    'currency': currency.name,
                    'amount': str(currency.round(amount)),
                    })
        #post['uf'] += '/%s' % str(self.id)
        client = self.flow_get_client()
        res = client.payments.post(post)
        if hasattr(res, 'payment_url'):
            tx.write({'state': 'pending'})
        return res

    def flow_getTransaction(self, post):
        client = self.flow_get_client()
        return client.payments.get(post['token'])


class PaymentTxFlow(models.Model):
    _inherit = 'payment.transaction'

    flow_token = fields.Char(
        string="Flow Token Transaction",
    )

    @api.model
    def _flow_form_get_tx_from_data(self, data):
        return self
        reference, txn_id = data.payment_id, data.transaction_id
        if not reference or not txn_id:
            error_msg = _('Flow: received data with missing reference (%s) or txn_id (%s)') % (reference, txn_id)
            _logger.warning(error_msg)
            raise ValidationError(error_msg)

        # find tx -> @TDENOTE use txn_id ?
        txs = self.env['payment.transaction'].search([
                    ('reference', '=', reference)])
        if not txs or len(txs) > 1:
            error_msg = 'Flow: received data for reference %s' % (reference)
            if not txs:
                error_msg += '; no order found'
            else:
                error_msg += '; multiple order found'
            _logger.info(error_msg)
            raise ValidationError(error_msg)
        return txs[0]

     
    def _flow_form_validate(self, data):
        codes = {
                '0': 'Transacción aprobada.',
                '-1': 'Rechazo de transacción.',
                '-2': 'Transacción debe reintentarse.',
                '-3': 'Error en transacción.',
                '-4': 'Rechazo de transacción.',
                '-5': 'Rechazo por error de tasa.',
                '-6': 'Excede cupo máximo mensual.',
                '-7': 'Excede límite diario por transacción.',
                '-8': 'Rubro no autorizado.',
            }
        status = data.status
        res = {
            'acquirer_reference': data.payment_id,
            'flow_token': data.token,
            'fees': data.payment_data['fee'],
        }
        if status in [2]:
            _logger.info('Validated flow payment for tx %s: set as done' % (self.reference))
            res.update(state='done', date=datetime.now())
            return self.write(res)
        elif status in [1, '-7']:
            _logger.warning('Received notification for flow payment %s: set as pending' % (self.reference))
            res.update(state='pending', state_message=data.get('pending_reason', ''))
            return self.write(res)
        else: #3 y 4
            error = 'Received unrecognized status for flow payment %s: %s, set as error' % (self.reference, codes[status].decode('utf-8'))
            _logger.warning(error)
            res.update(state='error', state_message=error)
            return self.write(res)

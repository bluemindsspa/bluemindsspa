# -*- coding: utf-'8' "-*-"|
from odoo import api, models, fields
import logging
_logger = logging.getLogger(__name__)


class PaymentAcquirerCurrency(models.Model):
    _inherit = 'payment.acquirer'

    currency_ids = fields.Many2many(
        'res.currency',
        string='Currencies',
        help="Use only these allowed currencies."
    )
    force_currency = fields.Boolean(
        string="Force Currency",
    )
    force_currency_id = fields.Many2one(
        'res.currency',
        string='Currency id',
    )

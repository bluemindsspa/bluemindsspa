# -*- coding: utf-8 -*-
from datetime import datetime
from .responses import PaymentsResponse, PaymentsCreateResponse


class Payments(object):
    ENDPOINT = '/payment/create'

    def __init__(self, client):
        self.client = client

    def get(self, notification_token):
        """
        Información completa del pago. Datos con los que fue creado y el estado
        actual del pago. Se obtiene del notification_token que envia flow
        cuando el pago es conciliado.
        """
        response = self.client.make_request('GET', '/payment/getStatus',
                    data={'token': notification_token})
        return PaymentsResponse.from_response(response)

    def post(self, data):
        """
        Crea un pago en flow y obtiene las URLs para redirección al usuario
        para que complete el pago.
        """
        if hasattr(data, 'expires_date'):
            if isinstance(data['expires_date'], datetime):
                data['expires_date'] = data['expires_date'].isoformat()
        response = self.client.make_request('POST', self.ENDPOINT, data=data)
        return PaymentsCreateResponse.from_response(response)

    def get_id(self, id):
        """
        Información completa del pago. Datos con los que fue creado y el estado
        actual del pago.
        """
        endpoint = "{0}/{1}/".format(self.ENDPOINT, id)
        response = self.client.make_request('GET', endpoint)
        return PaymentsResponse.from_response(response)

    def delete(self, id):
        """
        Solo se pueden borrar pagos que estén pendientes de pagar. Esta
        operación no puede deshacerse.
        """
        endpoint = "{0}/{1}/".format(self.ENDPOINT, id)
        response = self.client.make_request('DELETE', endpoint)
        return SuccessResponse.from_response(response)

    def post_refunds(self, id, amount=None):
        """
        Reembolsa total o parcialmente el monto de un pago. Esta operación solo
        se puede realizar en los comercios que recauden en cuenta flow y antes
        de la rendición de los fondos correspondientes.
        """
        data = None
        if amount:
            data = { 'amount': amount }
        endpoint = "{0}/{1}/refunds".format(self.ENDPOINT, id)
        response = self.client.make_request('POST', endpoint, data=data)
        return SuccessResponse.from_response(response)

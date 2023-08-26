from unittest import mock

from django.test import TestCase
from requests import Response
from rest_framework import status

from heartstringApp.models import Ticket
from heartstringApp.views import PaymentViewSet


# Create your tests here.

class PaymentViewSetTests(TestCase):

    def test_initiate_payment_success(self):
        """
        Test that the `initiate_payment()` method returns a success response when the payment is successful.
        """
        # Create a mock object for the `requests` library.
        requests_mock = mock.Mock()
        requests_mock.post.return_value = Response(status_code=200, json={"status": 1})

        # Create a ticket object.
        ticket = Ticket(id=1, total_amount=1000)

        # Call the `initiate_payment()` method.
        response = PaymentViewSet.initiate_payment(self.request, ticket_id=ticket.id, payment_method="mpesa")

        # Assert that the payment was successful.
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["success"], True)
        self.assertEqual(response.data["message"], "Payment request sent to MPESA number.")

    def test_initiate_payment_failure(self):
        """
        Test that the `initiate_payment()` method returns an error response when the payment is unsuccessful.
        """
        # Create a mock object for the `requests` library.
        requests_mock = mock.Mock()
        requests_mock.post.return_value = Response(status_code=400, json={"status": 0})

        # Create a ticket object.
        ticket = Ticket(id=1, total_amount=1000)

        # Call the `initiate_payment()` method.
        response = PaymentViewSet.initiate_payment(self.request, ticket_id=ticket.id, payment_method="mpesa")

        # Assert that the payment was unsuccessful.
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["success"], False)
        self.assertEqual(response.data["message"], "Payment request failed.")


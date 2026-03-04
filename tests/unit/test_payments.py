"""Unit tests for the StripePaymentService with mocked Stripe SDK."""

from unittest.mock import MagicMock, patch

import pytest

from stripe_service.payments import StripePaymentService


@pytest.fixture
def svc():
    return StripePaymentService(api_key="sk_test_unit_test_key")


class TestCustomerOperations:
    @patch("stripe.Customer.create")
    def test_create_customer_calls_stripe(self, mock_create, svc):
        mock_create.return_value = MagicMock(id="cus_123", email="user@test.com", name="Test")
        result = svc.create_customer("user@test.com", "Test")
        assert result.id == "cus_123"
        mock_create.assert_called_once_with(email="user@test.com", name="Test", metadata={})

    @patch("stripe.Customer.create")
    def test_create_customer_with_metadata(self, mock_create, svc):
        mock_create.return_value = MagicMock(id="cus_456")
        svc.create_customer("a@b.com", "A", metadata={"plan": "pro"})
        mock_create.assert_called_once_with(email="a@b.com", name="A", metadata={"plan": "pro"})

    @patch("stripe.Customer.retrieve")
    def test_get_customer(self, mock_retrieve, svc):
        mock_retrieve.return_value = MagicMock(id="cus_123")
        result = svc.get_customer("cus_123")
        assert result.id == "cus_123"

    @patch("stripe.Customer.modify")
    def test_update_customer(self, mock_modify, svc):
        mock_obj = MagicMock(id="cus_123")
        mock_obj.name = "Updated"
        mock_modify.return_value = mock_obj
        result = svc.update_customer("cus_123", name="Updated")
        assert result.name == "Updated"

    @patch("stripe.Customer.delete")
    def test_delete_customer(self, mock_delete, svc):
        mock_delete.return_value = MagicMock(id="cus_123", deleted=True)
        result = svc.delete_customer("cus_123")
        assert result.deleted is True


class TestPaymentIntentOperations:
    @patch("stripe.PaymentIntent.create")
    def test_create_payment_intent_basic(self, mock_create, svc):
        mock_create.return_value = MagicMock(id="pi_123", amount=1000, status="requires_payment_method")
        result = svc.create_payment_intent(amount=1000)
        assert result.amount == 1000
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["amount"] == 1000
        assert call_kwargs["currency"] == "usd"

    @patch("stripe.PaymentIntent.create")
    def test_create_payment_intent_with_customer(self, mock_create, svc):
        mock_create.return_value = MagicMock(id="pi_456")
        svc.create_payment_intent(amount=2000, customer_id="cus_123")
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["customer"] == "cus_123"

    @patch("stripe.PaymentIntent.cancel")
    def test_cancel_payment_intent(self, mock_cancel, svc):
        mock_cancel.return_value = MagicMock(id="pi_123", status="canceled")
        result = svc.cancel_payment_intent("pi_123")
        assert result.status == "canceled"


class TestRefundOperations:
    @patch("stripe.Refund.create")
    def test_full_refund(self, mock_create, svc):
        mock_create.return_value = MagicMock(id="re_123", amount=5000, status="succeeded")
        result = svc.create_refund("pi_123")
        assert result.status == "succeeded"
        mock_create.assert_called_once_with(payment_intent="pi_123")

    @patch("stripe.Refund.create")
    def test_partial_refund(self, mock_create, svc):
        mock_create.return_value = MagicMock(id="re_456", amount=2000, status="succeeded")
        result = svc.create_refund("pi_123", amount=2000, reason="requested_by_customer")
        mock_create.assert_called_once_with(payment_intent="pi_123", amount=2000, reason="requested_by_customer")


class TestProductAndPrice:
    @patch("stripe.Product.create")
    def test_create_product(self, mock_create, svc):
        mock_obj = MagicMock(id="prod_123")
        mock_obj.name = "BlackRoad Pro"
        mock_create.return_value = mock_obj
        result = svc.create_product("BlackRoad Pro", "Professional tier")
        assert result.name == "BlackRoad Pro"

    @patch("stripe.Price.create")
    def test_create_one_time_price(self, mock_create, svc):
        mock_create.return_value = MagicMock(id="price_123", unit_amount=2999)
        result = svc.create_price("prod_123", 2999)
        assert result.unit_amount == 2999
        call_kwargs = mock_create.call_args[1]
        assert "recurring" not in call_kwargs

    @patch("stripe.Price.create")
    def test_create_recurring_price(self, mock_create, svc):
        mock_create.return_value = MagicMock(id="price_456", unit_amount=999)
        svc.create_price("prod_123", 999, recurring_interval="month")
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["recurring"] == {"interval": "month"}


class TestSubscription:
    @patch("stripe.Subscription.create")
    def test_create_subscription(self, mock_create, svc):
        mock_create.return_value = MagicMock(id="sub_123", status="incomplete")
        result = svc.create_subscription("cus_123", "price_123")
        assert result.id == "sub_123"

    @patch("stripe.Subscription.modify")
    def test_cancel_subscription_at_period_end(self, mock_modify, svc):
        mock_modify.return_value = MagicMock(id="sub_123", cancel_at_period_end=True)
        result = svc.cancel_subscription("sub_123", at_period_end=True)
        assert result.cancel_at_period_end is True

    @patch("stripe.Subscription.cancel")
    def test_cancel_subscription_immediately(self, mock_cancel, svc):
        mock_cancel.return_value = MagicMock(id="sub_123", status="canceled")
        result = svc.cancel_subscription("sub_123", at_period_end=False)
        assert result.status == "canceled"

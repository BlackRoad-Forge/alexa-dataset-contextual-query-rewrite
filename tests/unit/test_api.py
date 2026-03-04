"""Unit tests for the API endpoints using mocked Stripe calls."""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["environment"] == "test"
        assert data["stripe_mode"] == "test"


class TestCustomerEndpoints:
    @patch("stripe.Customer.create")
    def test_create_customer(self, mock_create, client):
        mock_create.return_value = MagicMock(id="cus_test123", email="test@blackroad.com", name="Test User")
        resp = client.post("/api/customers", json={"email": "test@blackroad.com", "name": "Test User"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "cus_test123"
        assert data["email"] == "test@blackroad.com"
        mock_create.assert_called_once()

    @patch("stripe.Customer.retrieve")
    def test_get_customer(self, mock_retrieve, client):
        mock_retrieve.return_value = MagicMock(id="cus_test123", email="test@blackroad.com", name="Test User")
        resp = client.get("/api/customers/cus_test123")
        assert resp.status_code == 200
        assert resp.json()["id"] == "cus_test123"

    @patch("stripe.Customer.list")
    def test_list_customers(self, mock_list, client):
        mock_list.return_value = MagicMock(
            data=[
                MagicMock(id="cus_1", email="a@test.com", name="A"),
                MagicMock(id="cus_2", email="b@test.com", name="B"),
            ]
        )
        resp = client.get("/api/customers?limit=2")
        assert resp.status_code == 200
        assert len(resp.json()["customers"]) == 2

    @patch("stripe.Customer.delete")
    def test_delete_customer(self, mock_delete, client):
        mock_delete.return_value = MagicMock(id="cus_test123", deleted=True)
        resp = client.delete("/api/customers/cus_test123")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True


class TestPaymentIntentEndpoints:
    @patch("stripe.PaymentIntent.create")
    def test_create_payment_intent(self, mock_create, client):
        mock_create.return_value = MagicMock(
            id="pi_test123", amount=5000, currency="usd", status="requires_payment_method", client_secret="secret_123"
        )
        resp = client.post("/api/payment-intents", json={"amount": 5000, "currency": "usd"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "pi_test123"
        assert data["amount"] == 5000
        assert data["client_secret"] == "secret_123"

    @patch("stripe.PaymentIntent.retrieve")
    def test_get_payment_intent(self, mock_retrieve, client):
        mock_retrieve.return_value = MagicMock(id="pi_test123", amount=5000, status="requires_payment_method")
        resp = client.get("/api/payment-intents/pi_test123")
        assert resp.status_code == 200
        assert resp.json()["id"] == "pi_test123"

    @patch("stripe.PaymentIntent.cancel")
    def test_cancel_payment_intent(self, mock_cancel, client):
        mock_cancel.return_value = MagicMock(id="pi_test123", status="canceled")
        resp = client.post("/api/payment-intents/pi_test123/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "canceled"


class TestRefundEndpoints:
    @patch("stripe.Refund.create")
    def test_create_refund(self, mock_create, client):
        mock_create.return_value = MagicMock(id="re_test123", amount=5000, status="succeeded")
        resp = client.post("/api/refunds", json={"payment_intent_id": "pi_test123"})
        assert resp.status_code == 200
        assert resp.json()["id"] == "re_test123"
        assert resp.json()["status"] == "succeeded"

    @patch("stripe.Refund.create")
    def test_partial_refund(self, mock_create, client):
        mock_create.return_value = MagicMock(id="re_test456", amount=2000, status="succeeded")
        resp = client.post("/api/refunds", json={"payment_intent_id": "pi_test123", "amount": 2000})
        assert resp.status_code == 200
        assert resp.json()["amount"] == 2000


class TestProductAndPriceEndpoints:
    @patch("stripe.Product.create")
    def test_create_product(self, mock_create, client):
        mock_obj = MagicMock(id="prod_test123")
        mock_obj.name = "BlackRoad Pro"
        mock_create.return_value = mock_obj
        resp = client.post("/api/products", json={"name": "BlackRoad Pro", "description": "Pro tier"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "BlackRoad Pro"

    @patch("stripe.Price.create")
    def test_create_price(self, mock_create, client):
        mock_create.return_value = MagicMock(id="price_test123", unit_amount=2999, currency="usd")
        resp = client.post("/api/prices", json={"product_id": "prod_test123", "unit_amount": 2999})
        assert resp.status_code == 200
        assert resp.json()["unit_amount"] == 2999


class TestSubscriptionEndpoints:
    @patch("stripe.Subscription.create")
    def test_create_subscription(self, mock_create, client):
        mock_create.return_value = MagicMock(id="sub_test123", status="incomplete", customer="cus_test123")
        resp = client.post(
            "/api/subscriptions",
            json={"customer_id": "cus_test123", "price_id": "price_test123"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == "sub_test123"

    @patch("stripe.Subscription.retrieve")
    def test_get_subscription(self, mock_retrieve, client):
        mock_retrieve.return_value = MagicMock(id="sub_test123", status="active", customer="cus_test123")
        resp = client.get("/api/subscriptions/sub_test123")
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"


class TestCheckoutEndpoints:
    @patch("stripe.checkout.Session.create")
    def test_create_checkout_session(self, mock_create, client):
        mock_create.return_value = MagicMock(id="cs_test123", url="https://checkout.stripe.com/test")
        resp = client.post(
            "/api/checkout-sessions",
            json={
                "line_items": [{"price": "price_test123", "quantity": 1}],
                "success_url": "https://blackroad.com/success",
                "cancel_url": "https://blackroad.com/cancel",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["url"] == "https://checkout.stripe.com/test"


class TestPiRouting:
    def test_pi_status_no_nodes(self, client):
        resp = client.get("/api/pi/status")
        assert resp.status_code == 200
        assert resp.json()["nodes"] == []

    def test_pi_health_check_no_nodes(self, client):
        resp = client.post("/api/pi/health-check")
        assert resp.status_code == 404

    def test_pi_forward_no_nodes(self, client):
        resp = client.post("/api/pi/forward", json={"method": "GET", "path": "/test"})
        assert resp.status_code == 404

"""
End-to-end tests for the API server hitting real Stripe.

Run with: STRIPE_SECRET_KEY=sk_test_... pytest tests/e2e/test_api_e2e.py -m e2e -v
"""

import os
import pytest
from fastapi.testclient import TestClient

from stripe_service.config import Settings
from stripe_service.api import create_app

STRIPE_KEY = os.environ.get("STRIPE_SECRET_KEY", "")


def _has_real_test_key() -> bool:
    return STRIPE_KEY.startswith("sk_test_") and STRIPE_KEY != "sk_test_fake_key_for_unit_tests"


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not _has_real_test_key(), reason="Set STRIPE_SECRET_KEY to run"),
]


@pytest.fixture(scope="module")
def e2e_client():
    settings = Settings(
        stripe_secret_key=STRIPE_KEY,
        stripe_webhook_secret="whsec_test",
        environment="e2e_test",
    )
    app = create_app(settings)
    return TestClient(app)


class TestAPIHealthE2E:
    def test_health_check(self, e2e_client):
        resp = e2e_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["stripe_mode"] == "test"


class TestAPICustomerFlowE2E:
    def test_create_list_delete_customer(self, e2e_client):
        # Create
        resp = e2e_client.post("/api/customers", json={
            "email": "api-e2e@blackroad.com",
            "name": "API E2E Test",
        })
        assert resp.status_code == 200
        cust_id = resp.json()["id"]
        assert cust_id.startswith("cus_")

        # Get
        resp = e2e_client.get(f"/api/customers/{cust_id}")
        assert resp.status_code == 200
        assert resp.json()["email"] == "api-e2e@blackroad.com"

        # List
        resp = e2e_client.get("/api/customers?limit=5")
        assert resp.status_code == 200
        assert any(c["id"] == cust_id for c in resp.json()["customers"])

        # Delete
        resp = e2e_client.delete(f"/api/customers/{cust_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True


class TestAPIPaymentFlowE2E:
    def test_create_and_cancel_payment_intent(self, e2e_client):
        resp = e2e_client.post("/api/payment-intents", json={"amount": 7500, "currency": "usd"})
        assert resp.status_code == 200
        pi_id = resp.json()["id"]
        assert resp.json()["amount"] == 7500

        # Retrieve
        resp = e2e_client.get(f"/api/payment-intents/{pi_id}")
        assert resp.status_code == 200

        # Cancel
        resp = e2e_client.post(f"/api/payment-intents/{pi_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "canceled"


class TestAPIProductFlowE2E:
    def test_create_product_and_price(self, e2e_client):
        # Product
        resp = e2e_client.post("/api/products", json={
            "name": "API E2E Product",
            "description": "Test product",
        })
        assert resp.status_code == 200
        prod_id = resp.json()["id"]

        # Price
        resp = e2e_client.post("/api/prices", json={
            "product_id": prod_id,
            "unit_amount": 2499,
        })
        assert resp.status_code == 200
        assert resp.json()["unit_amount"] == 2499


class TestAPICheckoutE2E:
    def test_create_checkout_session(self, e2e_client):
        # First create a product and price
        resp = e2e_client.post("/api/products", json={"name": "Checkout E2E"})
        prod_id = resp.json()["id"]
        resp = e2e_client.post("/api/prices", json={"product_id": prod_id, "unit_amount": 999})
        price_id = resp.json()["id"]

        # Create checkout session
        resp = e2e_client.post("/api/checkout-sessions", json={
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": "https://blackroad.com/success",
            "cancel_url": "https://blackroad.com/cancel",
        })
        assert resp.status_code == 200
        assert resp.json()["url"] is not None

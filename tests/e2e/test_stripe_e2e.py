"""
End-to-end tests that hit the real Stripe Test API.

Run with: STRIPE_SECRET_KEY=sk_test_... pytest tests/e2e/ -m e2e -v

These tests create real objects in Stripe test mode and clean them up afterward.
They require a valid Stripe test secret key in the environment.
"""

import os
import pytest

from stripe_service.payments import StripePaymentService

STRIPE_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
SKIP_REASON = "Set STRIPE_SECRET_KEY=sk_test_... to run e2e tests"


def _has_real_test_key() -> bool:
    return STRIPE_KEY.startswith("sk_test_") and STRIPE_KEY != "sk_test_fake_key_for_unit_tests"


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not _has_real_test_key(), reason=SKIP_REASON),
]


@pytest.fixture(scope="module")
def svc():
    return StripePaymentService(api_key=STRIPE_KEY)


@pytest.fixture
def customer(svc):
    """Create a customer for the test and clean up afterward."""
    cust = svc.create_customer(
        email="e2e-test@blackroad.com",
        name="E2E Test User",
        metadata={"source": "e2e_test"},
    )
    yield cust
    try:
        svc.delete_customer(cust.id)
    except Exception:
        pass


class TestCustomerE2E:
    def test_create_and_retrieve_customer(self, svc, customer):
        fetched = svc.get_customer(customer.id)
        assert fetched.id == customer.id
        assert fetched.email == "e2e-test@blackroad.com"

    def test_update_customer(self, svc, customer):
        updated = svc.update_customer(customer.id, name="Updated E2E User")
        assert updated.name == "Updated E2E User"

    def test_list_customers_includes_created(self, svc, customer):
        customers = svc.list_customers(limit=100)
        ids = [c.id for c in customers]
        assert customer.id in ids


class TestPaymentIntentE2E:
    def test_create_payment_intent(self, svc):
        pi = svc.create_payment_intent(amount=2500, currency="usd", metadata={"test": "e2e"})
        assert pi.id.startswith("pi_")
        assert pi.amount == 2500
        assert pi.status == "requires_payment_method"
        # Cleanup
        svc.cancel_payment_intent(pi.id)

    def test_create_and_cancel_payment_intent(self, svc):
        pi = svc.create_payment_intent(amount=1000)
        cancelled = svc.cancel_payment_intent(pi.id)
        assert cancelled.status == "canceled"

    def test_create_payment_intent_with_customer(self, svc, customer):
        pi = svc.create_payment_intent(amount=3000, customer_id=customer.id)
        assert pi.customer == customer.id
        svc.cancel_payment_intent(pi.id)


class TestProductAndPriceE2E:
    def test_create_product_and_price(self, svc):
        product = svc.create_product(
            name="BlackRoad E2E Test Product",
            description="Created by e2e test",
            metadata={"e2e": "true"},
        )
        assert product.id.startswith("prod_")

        price = svc.create_price(
            product_id=product.id,
            unit_amount=1999,
            currency="usd",
        )
        assert price.id.startswith("price_")
        assert price.unit_amount == 1999

    def test_create_recurring_price(self, svc):
        product = svc.create_product(name="BlackRoad E2E Monthly")
        price = svc.create_price(
            product_id=product.id,
            unit_amount=999,
            currency="usd",
            recurring_interval="month",
        )
        assert price.recurring is not None
        assert price.recurring["interval"] == "month"


class TestCheckoutSessionE2E:
    def test_create_checkout_session(self, svc):
        product = svc.create_product(name="Checkout E2E Product")
        price = svc.create_price(product_id=product.id, unit_amount=4999)

        session = svc.create_checkout_session(
            line_items=[{"price": price.id, "quantity": 1}],
            success_url="https://blackroad.com/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="https://blackroad.com/cancel",
            mode="payment",
        )
        assert session.id.startswith("cs_")
        assert session.url is not None
        assert "checkout.stripe.com" in session.url


class TestFullPaymentFlowE2E:
    """Test the complete payment lifecycle: customer -> product -> price -> payment intent."""

    def test_full_payment_lifecycle(self, svc):
        # 1. Create customer
        customer = svc.create_customer(
            email="lifecycle-test@blackroad.com",
            name="Lifecycle Test",
        )
        assert customer.id.startswith("cus_")

        # 2. Create product + price
        product = svc.create_product(name="Lifecycle Test Product")
        price = svc.create_price(product_id=product.id, unit_amount=5000)

        # 3. Create payment intent for the customer
        pi = svc.create_payment_intent(
            amount=5000,
            customer_id=customer.id,
            metadata={"product": product.id, "price": price.id},
        )
        assert pi.amount == 5000
        assert pi.customer == customer.id

        # 4. Cancel (we can't complete without a real card in test mode)
        cancelled = svc.cancel_payment_intent(pi.id)
        assert cancelled.status == "canceled"

        # 5. Cleanup
        svc.delete_customer(customer.id)

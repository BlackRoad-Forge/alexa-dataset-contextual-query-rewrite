"""Core Stripe payment operations — customers, charges, subscriptions, refunds."""

import stripe
from typing import Any


class StripePaymentService:
    """Handles all Stripe payment operations."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        stripe.api_key = api_key

    # ── Customers ──────────────────────────────────────────────

    def create_customer(self, email: str, name: str, metadata: dict[str, str] | None = None) -> stripe.Customer:
        return stripe.Customer.create(
            email=email,
            name=name,
            metadata=metadata or {},
        )

    def get_customer(self, customer_id: str) -> stripe.Customer:
        return stripe.Customer.retrieve(customer_id)

    def list_customers(self, limit: int = 10) -> list[stripe.Customer]:
        return list(stripe.Customer.list(limit=limit).data)

    def update_customer(self, customer_id: str, **kwargs: Any) -> stripe.Customer:
        return stripe.Customer.modify(customer_id, **kwargs)

    def delete_customer(self, customer_id: str) -> stripe.Customer:
        return stripe.Customer.delete(customer_id)

    # ── Payment Intents ────────────────────────────────────────

    def create_payment_intent(
        self,
        amount: int,
        currency: str = "usd",
        customer_id: str | None = None,
        payment_method: str | None = None,
        metadata: dict[str, str] | None = None,
        automatic_payment_methods: bool = True,
    ) -> stripe.PaymentIntent:
        params: dict[str, Any] = {
            "amount": amount,
            "currency": currency,
            "metadata": metadata or {},
        }
        if customer_id:
            params["customer"] = customer_id
        if payment_method:
            params["payment_method"] = payment_method
            params["confirm"] = True
            params["automatic_payment_methods"] = {"enabled": True, "allow_redirects": "never"}
        else:
            params["automatic_payment_methods"] = {"enabled": automatic_payment_methods}
        return stripe.PaymentIntent.create(**params)

    def confirm_payment_intent(self, payment_intent_id: str, payment_method: str | None = None) -> stripe.PaymentIntent:
        params: dict[str, Any] = {}
        if payment_method:
            params["payment_method"] = payment_method
        return stripe.PaymentIntent.confirm(payment_intent_id, **params)

    def get_payment_intent(self, payment_intent_id: str) -> stripe.PaymentIntent:
        return stripe.PaymentIntent.retrieve(payment_intent_id)

    def cancel_payment_intent(self, payment_intent_id: str) -> stripe.PaymentIntent:
        return stripe.PaymentIntent.cancel(payment_intent_id)

    # ── Refunds ────────────────────────────────────────────────

    def create_refund(
        self,
        payment_intent_id: str,
        amount: int | None = None,
        reason: str | None = None,
    ) -> stripe.Refund:
        params: dict[str, Any] = {"payment_intent": payment_intent_id}
        if amount is not None:
            params["amount"] = amount
        if reason:
            params["reason"] = reason
        return stripe.Refund.create(**params)

    # ── Subscriptions ──────────────────────────────────────────

    def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        trial_period_days: int | None = None,
        metadata: dict[str, str] | None = None,
    ) -> stripe.Subscription:
        params: dict[str, Any] = {
            "customer": customer_id,
            "items": [{"price": price_id}],
            "metadata": metadata or {},
            "payment_behavior": "default_incomplete",
            "expand": ["latest_invoice.payment_intent"],
        }
        if trial_period_days:
            params["trial_period_days"] = trial_period_days
        return stripe.Subscription.create(**params)

    def cancel_subscription(self, subscription_id: str, at_period_end: bool = True) -> stripe.Subscription:
        if at_period_end:
            return stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
        return stripe.Subscription.cancel(subscription_id)

    def get_subscription(self, subscription_id: str) -> stripe.Subscription:
        return stripe.Subscription.retrieve(subscription_id)

    # ── Products & Prices ──────────────────────────────────────

    def create_product(self, name: str, description: str = "", metadata: dict[str, str] | None = None) -> stripe.Product:
        return stripe.Product.create(name=name, description=description, metadata=metadata or {})

    def create_price(
        self,
        product_id: str,
        unit_amount: int,
        currency: str = "usd",
        recurring_interval: str | None = None,
    ) -> stripe.Price:
        params: dict[str, Any] = {
            "product": product_id,
            "unit_amount": unit_amount,
            "currency": currency,
        }
        if recurring_interval:
            params["recurring"] = {"interval": recurring_interval}
        return stripe.Price.create(**params)

    # ── Checkout Sessions ──────────────────────────────────────

    def create_checkout_session(
        self,
        line_items: list[dict[str, Any]],
        success_url: str,
        cancel_url: str,
        mode: str = "payment",
        customer_id: str | None = None,
    ) -> stripe.checkout.Session:
        params: dict[str, Any] = {
            "line_items": line_items,
            "mode": mode,
            "success_url": success_url,
            "cancel_url": cancel_url,
        }
        if customer_id:
            params["customer"] = customer_id
        return stripe.checkout.Session.create(**params)

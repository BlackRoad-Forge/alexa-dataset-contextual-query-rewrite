"""FastAPI application — Stripe payment endpoints, webhook receiver, and Pi routing."""

import logging
from contextlib import asynccontextmanager
from typing import Any

import stripe
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr

from .config import Settings
from .payments import StripePaymentService
from .pi_router import PiRouter
from .webhooks import WebhookProcessor

logger = logging.getLogger(__name__)

# ── Request / Response Models ─────────────────────────────────

class CreateCustomerRequest(BaseModel):
    email: str
    name: str
    metadata: dict[str, str] = {}

class CreatePaymentIntentRequest(BaseModel):
    amount: int
    currency: str = "usd"
    customer_id: str | None = None
    payment_method: str | None = None
    metadata: dict[str, str] = {}

class CreateCheckoutRequest(BaseModel):
    line_items: list[dict[str, Any]]
    success_url: str
    cancel_url: str
    mode: str = "payment"
    customer_id: str | None = None

class CreateSubscriptionRequest(BaseModel):
    customer_id: str
    price_id: str
    trial_period_days: int | None = None
    metadata: dict[str, str] = {}

class CreateProductRequest(BaseModel):
    name: str
    description: str = ""
    metadata: dict[str, str] = {}

class CreatePriceRequest(BaseModel):
    product_id: str
    unit_amount: int
    currency: str = "usd"
    recurring_interval: str | None = None

class RefundRequest(BaseModel):
    payment_intent_id: str
    amount: int | None = None
    reason: str | None = None

class PiForwardRequest(BaseModel):
    method: str = "GET"
    path: str
    body: dict | None = None
    headers: dict | None = None

# ── App Factory ───────────────────────────────────────────────

def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    payments = StripePaymentService(api_key=settings.stripe_secret_key)
    webhooks = WebhookProcessor(webhook_secret=settings.stripe_webhook_secret)
    pi_router = PiRouter(
        node_urls=settings.pi_nodes,
        health_check_interval=settings.pi_health_check_interval,
    )

    # Register default webhook handlers
    @webhooks.on("payment_intent.succeeded")
    def handle_payment_succeeded(data, event):
        logger.info(f"Payment succeeded: {data['id']} for {data['amount']} {data['currency']}")
        return {"payment_id": data["id"], "amount": data["amount"]}

    @webhooks.on("payment_intent.payment_failed")
    def handle_payment_failed(data, event):
        logger.warning(f"Payment failed: {data['id']}")
        return {"payment_id": data["id"], "status": "failed"}

    @webhooks.on("customer.subscription.created")
    def handle_subscription_created(data, event):
        logger.info(f"Subscription created: {data['id']} for customer {data['customer']}")
        return {"subscription_id": data["id"]}

    @webhooks.on("customer.subscription.deleted")
    def handle_subscription_deleted(data, event):
        logger.info(f"Subscription cancelled: {data['id']}")
        return {"subscription_id": data["id"], "status": "cancelled"}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if pi_router.nodes:
            await pi_router.start_health_checks()
            logger.info(f"Started health checks for {len(pi_router.nodes)} Pi nodes")
        yield
        await pi_router.stop()

    app = FastAPI(
        title="BlackRoad Stripe Service",
        version="1.0.0",
        description="Stripe payment integration with Raspberry Pi routing",
        lifespan=lifespan,
    )

    # Store references for testing
    app.state.payments = payments
    app.state.webhooks = webhooks
    app.state.pi_router = pi_router
    app.state.settings = settings

    # ── Health ─────────────────────────────────────────────

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "environment": settings.environment,
            "stripe_mode": "test" if settings.is_test_mode else "live",
            "pi_nodes": pi_router.get_status() if pi_router.nodes else [],
        }

    # ── Customers ──────────────────────────────────────────

    @app.post("/api/customers")
    async def create_customer(req: CreateCustomerRequest):
        customer = payments.create_customer(email=req.email, name=req.name, metadata=req.metadata)
        return {"id": customer.id, "email": customer.email, "name": customer.name}

    @app.get("/api/customers/{customer_id}")
    async def get_customer(customer_id: str):
        try:
            customer = payments.get_customer(customer_id)
            return {"id": customer.id, "email": customer.email, "name": customer.name}
        except stripe.error.InvalidRequestError:
            raise HTTPException(status_code=404, detail="Customer not found")

    @app.get("/api/customers")
    async def list_customers(limit: int = 10):
        customers = payments.list_customers(limit=limit)
        return {"customers": [{"id": c.id, "email": c.email, "name": c.name} for c in customers]}

    @app.delete("/api/customers/{customer_id}")
    async def delete_customer(customer_id: str):
        try:
            payments.delete_customer(customer_id)
            return {"deleted": True, "id": customer_id}
        except stripe.error.InvalidRequestError:
            raise HTTPException(status_code=404, detail="Customer not found")

    # ── Payment Intents ────────────────────────────────────

    @app.post("/api/payment-intents")
    async def create_payment_intent(req: CreatePaymentIntentRequest):
        pi = payments.create_payment_intent(
            amount=req.amount,
            currency=req.currency,
            customer_id=req.customer_id,
            payment_method=req.payment_method,
            metadata=req.metadata,
        )
        return {
            "id": pi.id,
            "amount": pi.amount,
            "currency": pi.currency,
            "status": pi.status,
            "client_secret": pi.client_secret,
        }

    @app.get("/api/payment-intents/{payment_intent_id}")
    async def get_payment_intent(payment_intent_id: str):
        try:
            pi = payments.get_payment_intent(payment_intent_id)
            return {"id": pi.id, "amount": pi.amount, "status": pi.status}
        except stripe.error.InvalidRequestError:
            raise HTTPException(status_code=404, detail="PaymentIntent not found")

    @app.post("/api/payment-intents/{payment_intent_id}/cancel")
    async def cancel_payment_intent(payment_intent_id: str):
        try:
            pi = payments.cancel_payment_intent(payment_intent_id)
            return {"id": pi.id, "status": pi.status}
        except stripe.error.InvalidRequestError:
            raise HTTPException(status_code=404, detail="PaymentIntent not found")

    # ── Refunds ────────────────────────────────────────────

    @app.post("/api/refunds")
    async def create_refund(req: RefundRequest):
        refund = payments.create_refund(
            payment_intent_id=req.payment_intent_id,
            amount=req.amount,
            reason=req.reason,
        )
        return {"id": refund.id, "amount": refund.amount, "status": refund.status}

    # ── Products & Prices ──────────────────────────────────

    @app.post("/api/products")
    async def create_product(req: CreateProductRequest):
        product = payments.create_product(name=req.name, description=req.description, metadata=req.metadata)
        return {"id": product.id, "name": product.name}

    @app.post("/api/prices")
    async def create_price(req: CreatePriceRequest):
        price = payments.create_price(
            product_id=req.product_id,
            unit_amount=req.unit_amount,
            currency=req.currency,
            recurring_interval=req.recurring_interval,
        )
        return {"id": price.id, "unit_amount": price.unit_amount, "currency": price.currency}

    # ── Subscriptions ──────────────────────────────────────

    @app.post("/api/subscriptions")
    async def create_subscription(req: CreateSubscriptionRequest):
        sub = payments.create_subscription(
            customer_id=req.customer_id,
            price_id=req.price_id,
            trial_period_days=req.trial_period_days,
            metadata=req.metadata,
        )
        return {"id": sub.id, "status": sub.status, "customer": sub.customer}

    @app.get("/api/subscriptions/{subscription_id}")
    async def get_subscription(subscription_id: str):
        try:
            sub = payments.get_subscription(subscription_id)
            return {"id": sub.id, "status": sub.status, "customer": sub.customer}
        except stripe.error.InvalidRequestError:
            raise HTTPException(status_code=404, detail="Subscription not found")

    @app.post("/api/subscriptions/{subscription_id}/cancel")
    async def cancel_subscription(subscription_id: str, at_period_end: bool = True):
        sub = payments.cancel_subscription(subscription_id, at_period_end=at_period_end)
        return {"id": sub.id, "status": sub.status, "cancel_at_period_end": sub.cancel_at_period_end}

    # ── Checkout Sessions ──────────────────────────────────

    @app.post("/api/checkout-sessions")
    async def create_checkout_session(req: CreateCheckoutRequest):
        session = payments.create_checkout_session(
            line_items=req.line_items,
            success_url=req.success_url,
            cancel_url=req.cancel_url,
            mode=req.mode,
            customer_id=req.customer_id,
        )
        return {"id": session.id, "url": session.url}

    # ── Webhooks ───────────────────────────────────────────

    @app.post("/api/webhooks/stripe")
    async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
        if not stripe_signature:
            raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")
        payload = await request.body()
        try:
            result = await webhooks.process(payload, stripe_signature)
            return result
        except stripe.error.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid signature")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid payload")

    # ── Pi Routing ─────────────────────────────────────────

    @app.get("/api/pi/status")
    async def pi_status():
        if not pi_router.nodes:
            return {"nodes": [], "message": "No Pi nodes configured"}
        return {"nodes": pi_router.get_status()}

    @app.post("/api/pi/health-check")
    async def pi_health_check():
        if not pi_router.nodes:
            raise HTTPException(status_code=404, detail="No Pi nodes configured")
        results = await pi_router.check_all_nodes()
        return {"results": {url: healthy for url, healthy in results.items()}}

    @app.post("/api/pi/forward")
    async def pi_forward(req: PiForwardRequest):
        if not pi_router.nodes:
            raise HTTPException(status_code=404, detail="No Pi nodes configured")
        try:
            resp = await pi_router.forward_request(
                method=req.method,
                path=req.path,
                body=req.body,
                headers=req.headers,
            )
            return {"status_code": resp.status_code, "body": resp.text}
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))

    return app

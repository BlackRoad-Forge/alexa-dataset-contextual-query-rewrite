"""Stripe webhook handling — verify signatures and dispatch events."""

import stripe
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

EventHandler = type[None] | object  # callable


@dataclass
class WebhookProcessor:
    """Processes incoming Stripe webhook events with registered handlers."""

    webhook_secret: str
    _handlers: dict[str, list] = field(default_factory=dict)

    def on(self, event_type: str):
        """Decorator to register a handler for a Stripe event type."""
        def decorator(fn):
            self._handlers.setdefault(event_type, []).append(fn)
            return fn
        return decorator

    def register(self, event_type: str, handler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def verify_and_construct(self, payload: bytes, sig_header: str) -> stripe.Event:
        return stripe.Webhook.construct_event(payload, sig_header, self.webhook_secret)

    async def process(self, payload: bytes, sig_header: str) -> dict:
        try:
            event = self.verify_and_construct(payload, sig_header)
        except stripe.error.SignatureVerificationError:
            logger.warning("Webhook signature verification failed")
            raise
        except ValueError:
            logger.warning("Invalid webhook payload")
            raise

        event_type = event["type"]
        event_data = event["data"]["object"]

        logger.info(f"Processing webhook event: {event_type} [{event['id']}]")

        handlers = self._handlers.get(event_type, [])
        if not handlers:
            logger.info(f"No handlers for event type: {event_type}")
            return {"status": "ignored", "event_type": event_type}

        results = []
        for handler in handlers:
            try:
                result = handler(event_data, event)
                # Support async handlers
                if hasattr(result, "__await__"):
                    result = await result
                results.append({"handler": handler.__name__, "status": "ok", "result": result})
            except Exception as exc:
                logger.exception(f"Handler {handler.__name__} failed for {event_type}")
                results.append({"handler": handler.__name__, "status": "error", "error": str(exc)})

        return {"status": "processed", "event_type": event_type, "results": results}

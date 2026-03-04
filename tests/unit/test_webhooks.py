"""Unit tests for webhook processing."""

import json
from unittest.mock import MagicMock, patch

import pytest
import stripe

from stripe_service.webhooks import WebhookProcessor


@pytest.fixture
def processor():
    return WebhookProcessor(webhook_secret="whsec_test_secret")


class TestWebhookRegistration:
    def test_register_handler(self, processor):
        def handler(data, event):
            pass
        processor.register("payment_intent.succeeded", handler)
        assert len(processor._handlers["payment_intent.succeeded"]) == 1

    def test_decorator_registration(self, processor):
        @processor.on("checkout.session.completed")
        def handler(data, event):
            pass
        assert len(processor._handlers["checkout.session.completed"]) == 1

    def test_multiple_handlers_for_same_event(self, processor):
        processor.register("payment_intent.succeeded", lambda d, e: None)
        processor.register("payment_intent.succeeded", lambda d, e: None)
        assert len(processor._handlers["payment_intent.succeeded"]) == 2


class TestWebhookProcessing:
    @pytest.mark.asyncio
    @patch("stripe.Webhook.construct_event")
    async def test_process_known_event(self, mock_construct, processor):
        mock_event = {
            "id": "evt_123",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_123", "amount": 5000}},
        }
        mock_construct.return_value = mock_event

        results = []

        def handler(data, event):
            results.append(data["id"])
            return "handled"

        processor.register("payment_intent.succeeded", handler)
        result = await processor.process(b"payload", "sig_header")

        assert result["status"] == "processed"
        assert result["event_type"] == "payment_intent.succeeded"
        assert results == ["pi_123"]

    @pytest.mark.asyncio
    @patch("stripe.Webhook.construct_event")
    async def test_process_unknown_event(self, mock_construct, processor):
        mock_event = {
            "id": "evt_456",
            "type": "unknown.event.type",
            "data": {"object": {"id": "obj_123"}},
        }
        mock_construct.return_value = mock_event
        result = await processor.process(b"payload", "sig")
        assert result["status"] == "ignored"

    @pytest.mark.asyncio
    async def test_process_invalid_signature(self, processor):
        with patch("stripe.Webhook.construct_event", side_effect=stripe.error.SignatureVerificationError("bad", "sig")):
            with pytest.raises(stripe.error.SignatureVerificationError):
                await processor.process(b"payload", "bad_sig")

    @pytest.mark.asyncio
    @patch("stripe.Webhook.construct_event")
    async def test_handler_error_doesnt_crash(self, mock_construct, processor):
        mock_event = {
            "id": "evt_789",
            "type": "test.event",
            "data": {"object": {"id": "obj_789"}},
        }
        mock_construct.return_value = mock_event

        def bad_handler(data, event):
            raise ValueError("handler broke")

        processor.register("test.event", bad_handler)
        result = await processor.process(b"payload", "sig")
        assert result["status"] == "processed"
        assert result["results"][0]["status"] == "error"
        assert "handler broke" in result["results"][0]["error"]

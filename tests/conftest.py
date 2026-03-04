"""Shared test fixtures for unit and e2e tests."""

import os
import pytest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from stripe_service.config import Settings
from stripe_service.api import create_app
from stripe_service.payments import StripePaymentService


@pytest.fixture
def test_settings():
    """Settings with a test Stripe key (won't hit real API unless STRIPE_SECRET_KEY is set)."""
    key = os.environ.get("STRIPE_SECRET_KEY", "sk_test_fake_key_for_unit_tests")
    return Settings(
        stripe_secret_key=key,
        stripe_publishable_key="pk_test_fake",
        stripe_webhook_secret="whsec_test_fake",
        environment="test",
    )


@pytest.fixture
def app(test_settings):
    return create_app(test_settings)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def payment_service(test_settings):
    return StripePaymentService(api_key=test_settings.stripe_secret_key)

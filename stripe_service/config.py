"""Service configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    stripe_secret_key: str = Field(..., description="Stripe secret API key (sk_test_... or sk_live_...)")
    stripe_publishable_key: str = Field("", description="Stripe publishable key")
    stripe_webhook_secret: str = Field("", description="Stripe webhook signing secret")

    service_host: str = Field("0.0.0.0", description="Host to bind the service to")
    service_port: int = Field(8000, description="Port to bind the service to")
    environment: str = Field("development", description="Runtime environment")

    # Pi node routing
    pi_node_1: str = Field("", description="Raspberry Pi node 1 URL")
    pi_node_2: str = Field("", description="Raspberry Pi node 2 URL")
    pi_node_3: str = Field("", description="Raspberry Pi node 3 URL")
    pi_health_check_interval: int = Field(30, description="Seconds between Pi health checks")

    database_url: str = Field("sqlite:///./blackroad.db", description="Database connection URL")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def pi_nodes(self) -> list[str]:
        return [n for n in [self.pi_node_1, self.pi_node_2, self.pi_node_3] if n]

    @property
    def is_test_mode(self) -> bool:
        return self.stripe_secret_key.startswith("sk_test_")

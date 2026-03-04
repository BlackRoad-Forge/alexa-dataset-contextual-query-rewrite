"""Run the Stripe service: python -m stripe_service"""

import logging
import uvicorn

from .api import create_app
from .config import Settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

settings = Settings()
app = create_app(settings)

if __name__ == "__main__":
    uvicorn.run(
        "stripe_service.api:create_app",
        host=settings.service_host,
        port=settings.service_port,
        reload=settings.environment == "development",
        factory=True,
    )

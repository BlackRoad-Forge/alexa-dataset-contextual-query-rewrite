"""Raspberry Pi node routing — health checks, load balancing, and request forwarding."""

import asyncio
import logging
import time
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)


@dataclass
class PiNode:
    url: str
    healthy: bool = True
    last_check: float = 0.0
    response_time_ms: float = 0.0
    consecutive_failures: int = 0


class PiRouter:
    """Routes requests to Raspberry Pi nodes with health checking and failover."""

    def __init__(self, node_urls: list[str], health_check_interval: int = 30):
        self.nodes = [PiNode(url=url) for url in node_urls]
        self.health_check_interval = health_check_interval
        self._client = httpx.AsyncClient(timeout=10.0)
        self._check_task: asyncio.Task | None = None

    @property
    def healthy_nodes(self) -> list[PiNode]:
        return [n for n in self.nodes if n.healthy]

    def _pick_node(self) -> PiNode | None:
        """Pick the healthiest node with lowest response time."""
        healthy = self.healthy_nodes
        if not healthy:
            return None
        return min(healthy, key=lambda n: n.response_time_ms)

    async def check_node_health(self, node: PiNode) -> bool:
        try:
            start = time.monotonic()
            resp = await self._client.get(f"{node.url}/health")
            elapsed = (time.monotonic() - start) * 1000
            node.response_time_ms = elapsed
            node.last_check = time.time()

            if resp.status_code == 200:
                node.healthy = True
                node.consecutive_failures = 0
                return True

            node.consecutive_failures += 1
            node.healthy = node.consecutive_failures < 3
            return False
        except Exception:
            node.consecutive_failures += 1
            node.healthy = node.consecutive_failures < 3
            node.last_check = time.time()
            logger.warning(f"Health check failed for {node.url} (failures: {node.consecutive_failures})")
            return False

    async def check_all_nodes(self) -> dict[str, bool]:
        results = await asyncio.gather(
            *[self.check_node_health(node) for node in self.nodes],
            return_exceptions=True,
        )
        return {
            node.url: result if isinstance(result, bool) else False
            for node, result in zip(self.nodes, results)
        }

    async def forward_request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        headers: dict | None = None,
    ) -> httpx.Response:
        """Forward a request to the best available Pi node."""
        node = self._pick_node()
        if node is None:
            raise RuntimeError("No healthy Pi nodes available")

        url = f"{node.url}{path}"
        logger.info(f"Forwarding {method} {path} -> {url}")

        try:
            resp = await self._client.request(
                method=method,
                url=url,
                json=body,
                headers=headers or {},
            )
            return resp
        except Exception:
            node.consecutive_failures += 1
            node.healthy = False
            # Retry on next best node
            fallback = self._pick_node()
            if fallback is None:
                raise RuntimeError("All Pi nodes are down")
            fallback_url = f"{fallback.url}{path}"
            logger.info(f"Failing over to {fallback_url}")
            return await self._client.request(
                method=method,
                url=fallback_url,
                json=body,
                headers=headers or {},
            )

    async def start_health_checks(self) -> None:
        """Start periodic health check loop."""
        async def _loop():
            while True:
                await self.check_all_nodes()
                await asyncio.sleep(self.health_check_interval)
        self._check_task = asyncio.create_task(_loop())

    async def stop(self) -> None:
        if self._check_task:
            self._check_task.cancel()
        await self._client.aclose()

    def get_status(self) -> list[dict]:
        return [
            {
                "url": node.url,
                "healthy": node.healthy,
                "response_time_ms": round(node.response_time_ms, 2),
                "consecutive_failures": node.consecutive_failures,
                "last_check": node.last_check,
            }
            for node in self.nodes
        ]

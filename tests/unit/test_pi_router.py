"""Unit tests for the Raspberry Pi router with mocked HTTP."""

import pytest
import httpx
import respx

from stripe_service.pi_router import PiRouter, PiNode


PI_URLS = ["http://192.168.1.100:8080", "http://192.168.1.101:8080"]


@pytest.fixture
def router():
    return PiRouter(node_urls=PI_URLS, health_check_interval=5)


class TestPiNodeSelection:
    def test_healthy_nodes_all_up(self, router):
        assert len(router.healthy_nodes) == 2

    def test_healthy_nodes_one_down(self, router):
        router.nodes[0].healthy = False
        assert len(router.healthy_nodes) == 1
        assert router.healthy_nodes[0].url == PI_URLS[1]

    def test_pick_node_prefers_fastest(self, router):
        router.nodes[0].response_time_ms = 50.0
        router.nodes[1].response_time_ms = 20.0
        picked = router._pick_node()
        assert picked.url == PI_URLS[1]

    def test_pick_node_returns_none_when_all_down(self, router):
        for node in router.nodes:
            node.healthy = False
        assert router._pick_node() is None


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_success(self, router):
        with respx.mock:
            respx.get(f"{PI_URLS[0]}/health").respond(200, json={"status": "ok"})
            result = await router.check_node_health(router.nodes[0])
            assert result is True
            assert router.nodes[0].healthy is True
            assert router.nodes[0].consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_health_check_failure(self, router):
        with respx.mock:
            respx.get(f"{PI_URLS[0]}/health").respond(500)
            result = await router.check_node_health(router.nodes[0])
            assert result is False
            assert router.nodes[0].consecutive_failures == 1
            # Still healthy after 1 failure (threshold is 3)
            assert router.nodes[0].healthy is True

    @pytest.mark.asyncio
    async def test_health_check_three_failures_marks_unhealthy(self, router):
        with respx.mock:
            respx.get(f"{PI_URLS[0]}/health").respond(500)
            for _ in range(3):
                await router.check_node_health(router.nodes[0])
            assert router.nodes[0].healthy is False
            assert router.nodes[0].consecutive_failures == 3

    @pytest.mark.asyncio
    async def test_check_all_nodes(self, router):
        with respx.mock:
            respx.get(f"{PI_URLS[0]}/health").respond(200)
            respx.get(f"{PI_URLS[1]}/health").respond(200)
            results = await router.check_all_nodes()
            assert all(results.values())


class TestRequestForwarding:
    @pytest.mark.asyncio
    async def test_forward_get_request(self, router):
        with respx.mock:
            respx.get(f"{PI_URLS[0]}/api/data").respond(200, json={"data": "test"})
            resp = await router.forward_request("GET", "/api/data")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_forward_post_request(self, router):
        with respx.mock:
            respx.post(f"{PI_URLS[0]}/api/process").respond(201, json={"ok": True})
            resp = await router.forward_request("POST", "/api/process", body={"input": "test"})
            assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_forward_fails_with_no_healthy_nodes(self, router):
        for node in router.nodes:
            node.healthy = False
        with pytest.raises(RuntimeError, match="No healthy Pi nodes"):
            await router.forward_request("GET", "/test")


class TestGetStatus:
    def test_status_includes_all_nodes(self, router):
        status = router.get_status()
        assert len(status) == 2
        assert status[0]["url"] == PI_URLS[0]
        assert status[0]["healthy"] is True
        assert "response_time_ms" in status[0]

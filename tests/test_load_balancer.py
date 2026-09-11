import unittest
from unittest.mock import AsyncMock, patch

from load_balancer import LoadBalancer, ServerQueue


def make_server(server_id: str, online: bool = True) -> ServerQueue:
    server = ServerQueue(
        {"id": server_id, "name": server_id.upper(), "url": f"http://{server_id}"}
    )
    server.is_online = online
    return server


class SelectServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_busy_worker_stays_online_during_transient_health_timeout(self):
        balancer = LoadBalancer()
        gpu1 = make_server("gpu1")
        gpu1.current_job = "uploading-job"

        with patch(
            "load_balancer.comfyui_client.check_server",
            new=AsyncMock(return_value=False),
        ):
            await balancer._refresh_server_status(gpu1)

        self.assertTrue(gpu1.is_online)
        self.assertEqual("busy", gpu1.status)

    async def test_idle_worker_goes_offline_after_failed_health_probe(self):
        balancer = LoadBalancer()
        gpu1 = make_server("gpu1")

        with patch(
            "load_balancer.comfyui_client.check_server",
            new=AsyncMock(return_value=False),
        ):
            await balancer._refresh_server_status(gpu1)

        self.assertFalse(gpu1.is_online)

    async def test_round_robin_breaks_equal_load_ties(self):
        balancer = LoadBalancer()
        gpu1 = make_server("gpu1")
        gpu2 = make_server("gpu2")
        balancer.servers = [gpu1, gpu2]

        with patch.object(
            balancer, "_refresh_server_status", new=AsyncMock()
        ):
            first = await balancer._select_server()
            second = await balancer._select_server()

        self.assertIs(first, gpu1)
        self.assertIs(second, gpu2)

    async def test_idle_worker_wins_over_busy_worker(self):
        balancer = LoadBalancer()
        gpu1 = make_server("gpu1")
        gpu2 = make_server("gpu2")
        gpu1.current_job = "running-job"
        balancer.servers = [gpu1, gpu2]

        with patch.object(
            balancer, "_refresh_server_status", new=AsyncMock()
        ):
            selected = await balancer._select_server()

        self.assertIs(selected, gpu2)

    async def test_shorter_queue_wins_when_both_workers_busy(self):
        balancer = LoadBalancer()
        gpu1 = make_server("gpu1")
        gpu2 = make_server("gpu2")
        gpu1.current_job = "job-1"
        gpu2.current_job = "job-2"
        await gpu1.queue.put({"job_id": "queued-1"})
        balancer.servers = [gpu1, gpu2]

        with patch.object(
            balancer, "_refresh_server_status", new=AsyncMock()
        ):
            selected = await balancer._select_server()

        self.assertIs(selected, gpu2)

    async def test_returns_none_when_all_workers_are_offline(self):
        balancer = LoadBalancer()
        balancer.servers = [
            make_server("gpu1", online=False),
            make_server("gpu2", online=False),
        ]

        with patch.object(
            balancer, "_refresh_server_status", new=AsyncMock()
        ):
            selected = await balancer._select_server()

        self.assertIsNone(selected)


if __name__ == "__main__":
    unittest.main()

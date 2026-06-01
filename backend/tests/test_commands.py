"""
Starter tests for the command endpoint.
Candidates may extend these as part of their submission.
"""
import asyncio
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.dependencies import simulator
from app.models.drone import CommandRequest, GPSCoordinate, TelemetryFrame
from app.services.command_queue import CommandQueueService
from app.services.drone_simulator import DroneSimulator


@pytest.mark.asyncio
async def test_send_command_valid_drone():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/drones/drone-1/command",
            json={"type": "land"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["drone_id"] == "drone-1"
    assert data["status"] in ("accepted", "rejected")


@pytest.mark.asyncio
async def test_send_command_unknown_drone():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/drones/drone-does-not-exist/command",
            json={"type": "land"},
        )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_send_command_offline_drone(monkeypatch):
    monkeypatch.setattr(simulator, "get_drone_status", lambda drone_id: "offline")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/drones/drone-1/command",
            json={"type": "land"},
        )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_send_command_invalid_type():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/drones/drone-1/command",
            json={"type": "self_destruct"},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_pending_endpoint_unknown_drone():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/drones/nope/commands/pending")
    assert response.status_code == 404


async def _make_service(execute_impl):
    sim = DroneSimulator()
    sim.execute_command = execute_impl
    service = CommandQueueService(sim)
    await service.start()
    return service


@pytest.mark.asyncio
async def test_fifo_and_one_at_a_time():
    started: list[str] = []
    concurrent = 0
    max_concurrent = 0

    async def execute(drone_id, command):
        nonlocal concurrent, max_concurrent
        concurrent += 1
        max_concurrent = max(max_concurrent, concurrent)
        started.append(command.type)
        await asyncio.sleep(0.05)
        concurrent -= 1

    service = await _make_service(execute)
    try:
        for t in ("land", "hover", "return_home"):
            await service.enqueue("drone-1", CommandRequest(type=t))

        await asyncio.sleep(0.01)
        pending = service.get_pending("drone-1")
        assert pending.executing.type == "land"
        assert [p.type for p in pending.pending] == ["hover", "return_home"]

        await asyncio.sleep(0.25)
        assert started == ["land", "hover", "return_home"]
        assert max_concurrent == 1
        empty = service.get_pending("drone-1")
        assert empty.executing is None and empty.pending == []
    finally:
        await service.stop()


@pytest.mark.asyncio
async def test_offline_drains_queue_and_cancels_executing():
    cancelled = asyncio.Event()

    async def execute(drone_id, command):
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    service = await _make_service(execute)
    try:
        for t in ("land", "hover", "return_home"):
            await service.enqueue("drone-1", CommandRequest(type=t))

        await asyncio.sleep(0.01)
        assert service.get_pending("drone-1").executing is not None

        await service._on_frame(TelemetryFrame(
            drone_id="drone-1",
            timestamp=datetime.now(timezone.utc),
            battery=50.0,
            gps=GPSCoordinate(lat=0.0, lng=0.0, alt=0.0),
            speed=0.0,
            heading=0.0,
            status="offline",
        ))
        await asyncio.sleep(0.01)

        pending = service.get_pending("drone-1")
        assert pending.pending == []
        assert pending.executing is None
        assert cancelled.is_set()
    finally:
        await service.stop()

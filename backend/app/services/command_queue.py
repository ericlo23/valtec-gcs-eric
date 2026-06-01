import asyncio
import logging
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone

from app.models.drone import (
    CommandRequest,
    PendingCommandItem,
    PendingCommandsResponse,
)

logger = logging.getLogger(__name__)


@dataclass
class QueuedCommand:
    command_id: str
    command: CommandRequest
    submitted_at: datetime

    def to_item(self) -> PendingCommandItem:
        return PendingCommandItem(
            command_id=self.command_id,
            type=self.command.type,
            submitted_at=self.submitted_at,
        )


class CommandQueueService:
    def __init__(self, simulator):
        self._simulator = simulator
        self._pending: dict[str, deque[QueuedCommand]] = {}
        self._executing: dict[str, QueuedCommand | None] = {}
        self._exec_tasks: dict[str, asyncio.Task | None] = {}
        self._conds: dict[str, asyncio.Condition] = {}
        self._workers: list[asyncio.Task] = []

    async def start(self):
        for drone_id in self._simulator.get_drone_ids():
            self._ensure(drone_id)
        self._simulator.subscribe(self._on_frame)

    def _ensure(self, drone_id: str):
        if drone_id in self._conds:
            return
        self._pending[drone_id] = deque()
        self._executing[drone_id] = None
        self._exec_tasks[drone_id] = None
        self._conds[drone_id] = asyncio.Condition()
        self._workers.append(asyncio.create_task(self._worker(drone_id)))

    async def stop(self):
        self._simulator.unsubscribe(self._on_frame)
        for task in self._workers:
            task.cancel()
        for task in self._exec_tasks.values():
            if task and not task.done():
                task.cancel()
        self._workers.clear()

    async def enqueue(self, drone_id: str, command: CommandRequest) -> QueuedCommand:
        self._ensure(drone_id)
        item = QueuedCommand(
            command_id=str(uuid.uuid4())[:8],
            command=command,
            submitted_at=datetime.now(timezone.utc),
        )
        cond = self._conds[drone_id]
        async with cond:
            self._pending[drone_id].append(item)
            cond.notify()
        return item

    def get_pending(self, drone_id: str) -> PendingCommandsResponse:
        executing = self._executing.get(drone_id)
        return PendingCommandsResponse(
            drone_id=drone_id,
            executing=executing.to_item() if executing else None,
            pending=[qc.to_item() for qc in self._pending.get(drone_id, ())],
        )

    async def _worker(self, drone_id: str):
        cond = self._conds[drone_id]
        while True:
            async with cond:
                while not self._pending[drone_id]:
                    await cond.wait()
                item = self._pending[drone_id].popleft()
            await self._run_one(drone_id, item)

    async def _run_one(self, drone_id: str, item: QueuedCommand):
        self._executing[drone_id] = item
        exec_task = asyncio.create_task(
            self._simulator.execute_command(drone_id, item.command)
        )
        self._exec_tasks[drone_id] = exec_task
        try:
            await exec_task
            logger.info(
                "command %s (%s) completed on %s",
                item.command_id, item.command.type, drone_id,
            )
        except asyncio.CancelledError:
            if not exec_task.cancelled():
                exec_task.cancel()
                raise
            logger.warning(
                "command %s aborted on %s (drone went offline)",
                item.command_id, drone_id,
            )
        except Exception:
            logger.exception(
                "command %s (type=%s, payload=%s) failed on %s",
                item.command_id, item.command.type, item.command.payload, drone_id,
            )
        finally:
            self._executing[drone_id] = None
            self._exec_tasks[drone_id] = None

    async def _on_frame(self, frame):
        if frame.status == "offline":
            self._drain(frame.drone_id)

    def _drain(self, drone_id: str):
        pending = self._pending.get(drone_id)
        if pending:
            logger.warning(
                "draining %d pending command(s) for offline drone %s",
                len(pending), drone_id,
            )
            pending.clear()
        exec_task = self._exec_tasks.get(drone_id)
        if exec_task and not exec_task.done():
            exec_task.cancel()

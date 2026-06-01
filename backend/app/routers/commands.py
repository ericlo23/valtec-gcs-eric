import logging

from fastapi import APIRouter, HTTPException
from app.models.drone import CommandRequest, CommandResponse, PendingCommandsResponse
from app.dependencies import simulator, command_queue_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/drones", tags=["commands"])


# -----------------------------------------------------------------------
# BUG #2 — This endpoint has multiple error handling problems.
#
# Your task (see ASSIGNMENT.md Task 2):
#   Find all the issues and fix them. Do not change the URL or schema.
# -----------------------------------------------------------------------

@router.post("/{drone_id}/command", response_model=CommandResponse)
async def send_command(drone_id: str, command: CommandRequest):
    status = simulator.get_drone_status(drone_id)
    if status is None:
        raise HTTPException(
            status_code=404,
            detail=f"Drone '{drone_id}' not found",
        )

    if status == "offline":
        raise HTTPException(
            status_code=409,
            detail=f"Drone '{drone_id}' is offline and cannot accept commands",
        )

    item = await command_queue_service.enqueue(drone_id, command)

    return CommandResponse(
        command_id=item.command_id,
        drone_id=drone_id,
        type=command.type,
        status="accepted",
        message=f"Command {command.type} queued for {drone_id}",
    )


@router.get("/{drone_id}/commands/pending", response_model=PendingCommandsResponse)
async def get_pending_commands(drone_id: str):
    if simulator.get_drone_status(drone_id) is None:
        raise HTTPException(
            status_code=404,
            detail=f"Drone '{drone_id}' not found",
        )

    return command_queue_service.get_pending(drone_id)

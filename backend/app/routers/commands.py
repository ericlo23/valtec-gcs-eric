import logging

from fastapi import APIRouter, HTTPException
from app.models.drone import CommandRequest, CommandResponse
from app.services.command_service import CommandService
from app.dependencies import simulator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/drones", tags=["commands"])
command_service = CommandService()


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

    try:
        result = await command_service.execute(drone_id, command)
    except Exception:
        logger.exception(
            "Failed to execute command '%s' for drone '%s' (payload=%s)",
            command.type, drone_id, command.payload,
        )
        raise

    return result

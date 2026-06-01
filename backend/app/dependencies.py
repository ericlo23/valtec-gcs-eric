from app.services.drone_simulator import DroneSimulator
from app.services.command_queue import CommandQueueService

# Single shared instances across the entire app
simulator = DroneSimulator()
command_queue_service = CommandQueueService(simulator)

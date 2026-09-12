"""
Project Vulcan: Standalone Runner Worker Process (BKND-18)
Executable entrypoint for running decoupled execution worker fleets.
Usage:
    python -m app.workers.runner_worker --concurrency 75
"""
import argparse
import logging
import os
import signal
import sys
import time

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.config import container
from app.api.websockets import ws_hub
from app.workers.execution_worker import ExecutionWorkerFleet

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s"
)
logger = logging.getLogger("vulcan.runner_worker")


def main():
    parser = argparse.ArgumentParser(description="Vulcan Decoupled Execution Worker Fleet (BKND-18)")
    parser.add_argument("--concurrency", type=int, default=int(os.getenv("VULCAN_WORKER_CONCURRENCY", "75")), help="Worker pool size")
    parser.add_argument("--fleet-name", type=str, default=os.getenv("VULCAN_FLEET_NAME", "vulcan-worker-pod"), help="Fleet identifier")
    args = parser.parse_args()

    logger.info("Initializing Vulcan Execution Worker Fleet [%s] with concurrency=%d", args.fleet_name, args.concurrency)
    logger.info("Connected to Job Queue: %s (depth: %d)", type(container.job_queue).__name__, container.job_queue.queue_depth())

    fleet = ExecutionWorkerFleet(
        job_queue=container.job_queue,
        container=container,
        ws_hub=ws_hub,
        concurrency=args.concurrency,
        fleet_name=args.fleet_name
    )

    def _signal_handler(sig, frame):
        logger.info("Received termination signal (%s). Initiating graceful fleet drain...", sig)
        fleet.stop(timeout_seconds=10.0)
        logger.info("Fleet shutdown complete. Exiting.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    fleet.start()
    logger.info("Worker fleet active. Listening for Redis Streams / Queue dispatch events...")

    try:
        while fleet.is_running:
            time.sleep(15)
            logger.info("Heartbeat: Fleet [%s] active (%d workers). Queue depth: %d",
                        args.fleet_name, fleet.active_worker_count(), container.job_queue.queue_depth())
    except KeyboardInterrupt:
        _signal_handler(signal.SIGINT, None)


if __name__ == "__main__":
    main()

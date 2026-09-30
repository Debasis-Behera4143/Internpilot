"""Automated Background Ingestion Scheduler Service.

Runs periodic opportunity ingestion in a non-blocking background thread
during FastAPI application execution so newly posted jobs from Telegram,
ATS feeds, and configured sources automatically appear on the site.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from backend.utils.config import settings
from backend.utils.logger import get_logger

logger = get_logger("scheduler_service")

# Global background task handle
_scheduler_task: Optional[asyncio.Task] = None
_last_run_time: Optional[str] = None
_last_run_result: Optional[Dict[str, Any]] = None
_is_running_ingestion: bool = False


async def _execute_ingestion_job() -> Optional[Dict[str, Any]]:
    """Execute ingestion pipeline in a thread pool without blocking event loop."""
    global _last_run_time, _last_run_result, _is_running_ingestion
    if _is_running_ingestion:
        logger.info("Ingestion job already in progress, skipping overlapping run.")
        return None

    _is_running_ingestion = True
    try:
        from backend.services.ingestion_service import run_ingestion_pipeline

        logger.info("Background scheduler starting automated opportunity ingestion...")
        report = await asyncio.to_thread(run_ingestion_pipeline)
        _last_run_time = datetime.now(timezone.utc).isoformat()
        _last_run_result = report

        saved = report.get("saved", 0)
        verified = report.get("verified", 0)
        found = report.get("found", 0)
        logger.info(
            f"Background ingestion completed successfully: {found} found, "
            f"{saved} newly saved, {verified} verified and published."
        )
        return report
    except Exception as e:
        logger.error(f"Error during background ingestion execution: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
    finally:
        _is_running_ingestion = False


async def _scheduler_loop():
    """Continuous periodic loop running ingestion at configured intervals."""
    logger.info(
        f"Scheduler initialized: interval={settings.AUTO_INGEST_INTERVAL_MINUTES}m, "
        f"startup_ingest={settings.AUTO_INGEST_ON_STARTUP}"
    )

    # 1. Startup run (after short delay to let server finish startup)
    if settings.AUTO_INGEST_ON_STARTUP:
        try:
            await asyncio.sleep(4)
            logger.info("Running initial startup opportunity ingestion...")
            await _execute_ingestion_job()
        except asyncio.CancelledError:
            logger.info("Background scheduler cancelled during startup delay.")
            return
        except Exception as e:
            logger.warning(f"Initial startup ingestion notice: {e}")

    # 2. Periodic loop
    interval_seconds = max(60, settings.AUTO_INGEST_INTERVAL_MINUTES * 60)
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            logger.info("Periodic interval elapsed; triggering scheduled ingestion...")
            await _execute_ingestion_job()
        except asyncio.CancelledError:
            logger.info("Background scheduler loop gracefully stopped.")
            break
        except Exception as e:
            logger.error(f"Unexpected error in background scheduler loop: {e}", exc_info=True)
            await asyncio.sleep(30)


def start_background_scheduler():
    """Start the asynchronous background scheduler task."""
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        loop = asyncio.get_event_loop()
        _scheduler_task = loop.create_task(_scheduler_loop())
        logger.info("Background opportunity scheduler task created.")


def stop_background_scheduler():
    """Stop and cancel the background scheduler task."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        logger.info("Stopping background opportunity scheduler task...")
        _scheduler_task.cancel()
        _scheduler_task = None


def get_scheduler_status() -> Dict[str, Any]:
    """Return current status and metrics of the background ingestion scheduler."""
    is_active = _scheduler_task is not None and not _scheduler_task.done()
    return {
        "active": is_active,
        "is_ingesting": _is_running_ingestion,
        "interval_minutes": settings.AUTO_INGEST_INTERVAL_MINUTES,
        "last_run_time": _last_run_time,
        "last_run_result": _last_run_result
    }


async def trigger_immediate_ingestion() -> Dict[str, Any]:
    """Trigger an immediate ingestion run on-demand."""
    return await _execute_ingestion_job()

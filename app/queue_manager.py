import asyncio
import json
import logging
import time
import uuid
from pathlib import Path

from app.inference import run_inference
from app.schemas import ImpresionClinicaRequest, JobStatus

logger = logging.getLogger(__name__)

JOBS_FILE = Path("jobs.json")


class QueueManager:
    def __init__(self, maxsize: int = 50, job_ttl_seconds: int = 3600):
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self.jobs: dict[str, dict] = {}
        self.job_ttl_seconds = job_ttl_seconds
        self._worker_task: asyncio.Task | None = None
        self._load_persisted_jobs()

    def _load_persisted_jobs(self):
        """Load pending jobs from disk on startup."""
        if JOBS_FILE.exists():
            try:
                data = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
                for job_id, job_data in data.items():
                    if job_data["status"] in ("queued", "processing"):
                        job_data["status"] = "queued"
                        self.jobs[job_id] = job_data
                logger.info("Loaded %d persisted jobs", len(self.jobs))
            except Exception:
                logger.exception("Failed to load persisted jobs")

    def _persist_jobs(self):
        """Save pending/processing jobs to disk."""
        pending = {
            jid: jdata
            for jid, jdata in self.jobs.items()
            if jdata["status"] in ("queued", "processing")
        }
        try:
            JOBS_FILE.write_text(
                json.dumps(pending, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("Failed to persist jobs")

    async def start(self):
        """Start the background worker and re-enqueue persisted jobs."""
        self._worker_task = asyncio.create_task(self._worker())
        # Re-enqueue persisted jobs
        for job_id, job_data in list(self.jobs.items()):
            if job_data["status"] == "queued":
                payload = ImpresionClinicaRequest(**job_data["payload"])
                await self.queue.put((job_id, payload))
        # Start cleanup task
        asyncio.create_task(self._cleanup_loop())

    async def stop(self):
        """Persist jobs and cancel the worker."""
        self._persist_jobs()
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    def enqueue(self, payload: ImpresionClinicaRequest) -> str:
        """Add a job to the queue. Returns job_id. Raises if queue is full."""
        job_id = str(uuid.uuid4())
        self.jobs[job_id] = {
            "status": "queued",
            "job_id": job_id,
            "impresion_clinica": None,
            "error": None,
            "payload": payload.model_dump(),
            "created_at": time.time(),
        }
        try:
            self.queue.put_nowait((job_id, payload))
        except asyncio.QueueFull:
            del self.jobs[job_id]
            raise
        self._persist_jobs()
        return job_id

    def get_status(self, job_id: str) -> JobStatus | None:
        """Get the current status of a job."""
        job_data = self.jobs.get(job_id)
        if job_data is None:
            return None
        return JobStatus(
            status=job_data["status"],
            job_id=job_data["job_id"],
            impresion_clinica=job_data.get("impresion_clinica"),
            error=job_data.get("error"),
        )

    @property
    def queue_size(self) -> int:
        return self.queue.qsize()

    async def _worker(self):
        """Process one job at a time from the queue."""
        while True:
            job_id, payload = await self.queue.get()
            start_time = time.time()
            self.jobs[job_id]["status"] = "processing"
            self._persist_jobs()
            try:
                result = await asyncio.wait_for(
                    run_inference(payload),
                    timeout=120.0,
                )
                self.jobs[job_id]["status"] = "done"
                self.jobs[job_id]["impresion_clinica"] = result
                elapsed = time.time() - start_time
                logger.info("Job %s completed in %.1fs", job_id, elapsed)
            except asyncio.TimeoutError:
                self.jobs[job_id]["status"] = "failed"
                self.jobs[job_id]["error"] = "Timeout: Ollama no respondió en 120s"
                logger.error("Job %s timed out", job_id)
            except Exception as exc:
                self.jobs[job_id]["status"] = "failed"
                self.jobs[job_id]["error"] = str(exc)
                logger.exception("Job %s failed", job_id)
            finally:
                self._persist_jobs()
                self.queue.task_done()

    async def _cleanup_loop(self):
        """Remove completed/failed jobs older than TTL."""
        while True:
            await asyncio.sleep(300)  # Check every 5 minutes
            now = time.time()
            expired = [
                jid
                for jid, jdata in self.jobs.items()
                if jdata["status"] in ("done", "failed")
                and (now - jdata.get("created_at", 0)) > self.job_ttl_seconds
            ]
            for jid in expired:
                del self.jobs[jid]
            if expired:
                logger.info("Cleaned up %d expired jobs", len(expired))

import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

from ..services.pdf_processing import process_pdf


_executor: Optional[ThreadPoolExecutor] = None
_lock = threading.Lock()
_jobs: Dict[str, Dict[str, Any]] = {}


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        # Limit workers to avoid overloading CPU/GPU
        _executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ingest")
    return _executor


def submit_ingest_job(file_path: str, filename: str, owner_user_id: int, content_hash: str, document_id: int | None = None) -> str:
    job_id = uuid.uuid4().hex
    with _lock:
        _jobs[job_id] = {
            "state": "processing",
            "message": f"Processing {filename}",
            "result": None,
        }

    def _run():
        try:
            result = process_pdf(file_path, filename, owner_user_id=owner_user_id, content_hash=content_hash, document_id=document_id)
            with _lock:
                _jobs[job_id]["state"] = "completed"
                _jobs[job_id]["message"] = f"Processed {filename} successfully"
                _jobs[job_id]["result"] = result
        except Exception as exc:
            with _lock:
                _jobs[job_id]["state"] = "failed"
                _jobs[job_id]["message"] = f"Failed: {type(exc).__name__}: {exc}"
                _jobs[job_id]["result"] = None

    _get_executor().submit(_run)
    return job_id


def get_job_status(job_id: str) -> Dict[str, Any]:
    with _lock:
        data = _jobs.get(job_id)
        if not data:
            return {"state": "not_found", "message": "Job not found"}
        return {**data, "job_id": job_id}


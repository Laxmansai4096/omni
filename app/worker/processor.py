"""
Enterprise Asynchronous Worker Engine
Consumes document processing tasks from Azure Service Bus queue, executes AI extraction, and updates job state.
"""

import json
import logging
import threading
import time
import os
from typing import Optional

from app.config import settings
from app.services.azure_service_bus import service_bus_service
from app.services.azure_storage import storage_service
from app.services.azure_doc_intel import AzureDocIntelService
from app.services.telemetry import trace_span, extract_trace_context, get_tracer
from app.database.job_store import update_job_stage, save_job_result, get_job
from app.database.store import save_document_to_db

logger = logging.getLogger("worker_processor")
logger.setLevel(logging.INFO)

class DocumentQueueWorker:
    def __init__(self):
        self._doc_intel = AzureDocIntelService()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start_background(self):
        """Starts worker loop in a background daemon thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, name="AzureServiceBusWorker", daemon=True)
        self._thread.start()
        logger.info("[Worker] Started background Service Bus queue consumer thread.")

    def stop(self):
        """Stops the worker loop gracefully."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        logger.info("[Worker] Stopped Service Bus worker.")

    def _run_loop(self):
        """Main Service Bus receiver loop."""
        while self._running:
            try:
                if not service_bus_service.is_configured:
                    time.sleep(5)
                    continue

                receiver = service_bus_service.get_queue_receiver()
                if not receiver:
                    time.sleep(5)
                    continue

                with receiver:
                    logger.info("[Worker] Listening for incoming messages on 'ai-jobs-queue'...")
                    while self._running:
                        messages = receiver.receive_messages(max_message_count=1, max_wait_time=5)
                        if not messages:
                            continue
                        for msg in messages:
                            if not self._running:
                                break
                            try:
                                self.process_message(msg, receiver)
                            except Exception as e:
                                logger.error(f"[Worker] Unhandled error processing message: {e}")
                                try:
                                    receiver.abandon_message(msg)
                                except Exception:
                                    pass
            except Exception as e:
                logger.error(f"[Worker] Queue consumer loop encountered error: {e}. Retrying in 5 seconds...")
                time.sleep(5)

    def process_message(self, msg, receiver):
        """Processes an individual Service Bus message with distributed tracing and stage tracking."""
        body_str = str(msg)
        try:
            data = json.loads(body_str)
        except Exception:
            logger.error("[Worker] Failed to parse message body as JSON. Dead-lettering...")
            receiver.dead_letter_message(msg, reason="InvalidPayload", error_description="Non-JSON payload")
            return

        job_id = data.get("job_id")
        file_name = data.get("file_name", "document.pdf")
        blob_name = data.get("blob_name")

        if not job_id or not blob_name:
            receiver.dead_letter_message(msg, reason="MissingRequiredFields", error_description="job_id or blob_name missing")
            return

        logger.info(f"[Worker] Picked up job '{job_id}' for file '{file_name}' from Service Bus.")

        # Stage 1: Fetching payload from Blob Storage
        update_job_stage(job_id, status="PROCESSING", progress_pct=20, current_stage="FETCHING_FROM_AZURE_BLOB")
        file_bytes = storage_service.download_document(blob_name)
        if not file_bytes:
            err_msg = f"Failed to retrieve blob {blob_name} from storage"
            logger.error(f"[Worker] {err_msg}")
            update_job_stage(job_id, status="FAILED", progress_pct=20, current_stage="FETCH_FAILED", error_message=err_msg)
            receiver.dead_letter_message(msg, reason="BlobNotFound", error_description=err_msg)
            return

        # Stage 2: OCR & Layout Extraction via Document Intelligence
        update_job_stage(job_id, status="PROCESSING", progress_pct=50, current_stage="AZURE_DOCUMENT_INTELLIGENCE_OCR")
        with trace_span("worker.process_document", {"job_id": job_id, "file_name": file_name, "bytes": len(file_bytes)}):
            try:
                result = self._doc_intel.analyze_document_bytes(file_bytes, file_name)
                result.document_id = job_id  # Ensure alignment with job ID

                # Stage 3: Azure OpenAI Vision Deep Analysis
                update_job_stage(job_id, status="PROCESSING", progress_pct=85, current_stage="AZURE_OPENAI_VISION_ANALYSIS")
                
                # Check for charts/diagrams and enhance if present
                result_dict = result.model_dump()

                # Stage 4: Persist structured result & Complete
                update_job_stage(job_id, status="PROCESSING", progress_pct=95, current_stage="PERSISTING_STRUCTURED_DATA")
                save_job_result(job_id, result_dict)
                save_document_to_db(job_id, file_name, len(file_bytes), "async_queue", result_dict)

                # Set job status to COMPLETED (100%) so SSE streaming and UI polling resolve immediately
                update_job_stage(job_id, status="COMPLETED", progress_pct=100, current_stage="PROCESSING_COMPLETED")

                # Publish completion notification
                service_bus_service.publish_result(job_id, "COMPLETED", {
                    "pages": result.summary.total_pages,
                    "elements": result.summary.total_elements,
                    "processing_time_ms": result.summary.processing_time_ms
                })

                # Complete message from queue
                receiver.complete_message(msg)
                logger.info(f"[Worker] Successfully processed and marked COMPLETED for job '{job_id}' ({result.summary.total_elements} elements).")

            except Exception as e:
                err_str = str(e)
                logger.error(f"[Worker] Processing exception for job {job_id}: {err_str}", exc_info=True)
                update_job_stage(job_id, status="FAILED", progress_pct=50, current_stage="EXTRACTION_FAILED", error_message=err_str)
                receiver.dead_letter_message(msg, reason="ProcessingError", error_description=err_str[:250])

    def process_job_direct(self, job_id: str, file_name: str, blob_name: str, file_bytes: Optional[bytes] = None):
        """Directly processes a job without requiring Service Bus queue message."""
        logger.info(f"[Worker:Direct] Processing job '{job_id}' for file '{file_name}'.")
        update_job_stage(job_id, status="PROCESSING", progress_pct=20, current_stage="FETCHING_FROM_AZURE_BLOB")
        if not file_bytes:
            file_bytes = storage_service.download_document(blob_name)
        if not file_bytes:
            err_msg = f"Failed to retrieve blob {blob_name} from storage"
            logger.error(f"[Worker:Direct] {err_msg}")
            update_job_stage(job_id, status="FAILED", progress_pct=20, current_stage="FETCH_FAILED", error_message=err_msg)
            return

        update_job_stage(job_id, status="PROCESSING", progress_pct=50, current_stage="AZURE_DOCUMENT_INTELLIGENCE_OCR")
        with trace_span("worker.process_document_direct", {"job_id": job_id, "file_name": file_name, "bytes": len(file_bytes)}):
            try:
                result = self._doc_intel.analyze_document_bytes(file_bytes, file_name)
                result.document_id = job_id
                
                update_job_stage(job_id, status="PROCESSING", progress_pct=85, current_stage="AZURE_OPENAI_VISION_ANALYSIS")
                result_dict = result.model_dump()

                update_job_stage(job_id, status="PROCESSING", progress_pct=95, current_stage="PERSISTING_STRUCTURED_DATA")
                save_job_result(job_id, result_dict)
                save_document_to_db(job_id, file_name, len(file_bytes), "async_queue", result_dict)

                update_job_stage(job_id, status="COMPLETED", progress_pct=100, current_stage="PROCESSING_COMPLETED")
                logger.info(f"[Worker:Direct] Successfully processed job '{job_id}' ({result.summary.total_elements} elements).")
            except Exception as e:
                err_str = str(e)
                logger.error(f"[Worker:Direct] Processing exception for job {job_id}: {err_str}", exc_info=True)
                update_job_stage(job_id, status="FAILED", progress_pct=50, current_stage="EXTRACTION_FAILED", error_message=err_str)

# Global singleton worker

worker_instance = DocumentQueueWorker()

if __name__ == "__main__":
    # Standalone execution mode for dedicated worker container
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    print("=== Starting Standalone Azure Service Bus Document Worker ===")
    worker = DocumentQueueWorker()
    worker._run_loop()

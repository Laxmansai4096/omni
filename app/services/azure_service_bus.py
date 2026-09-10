"""
Azure Service Bus Enterprise Messaging Service
Enterprise Forward Deployed Engineering (FDE) decoupled queuing and load buffering.
"""

import json
import logging
import time
from typing import Optional, Dict, Any, Callable
from azure.servicebus import ServiceBusClient, ServiceBusMessage, ServiceBusReceiver, ServiceBusSender, TransportType
from app.config import settings
from app.services.telemetry import trace_span, inject_trace_context, extract_trace_context

logger = logging.getLogger("azure_service_bus")
logger.setLevel(logging.INFO)

class AzureServiceBusService:
    def __init__(self):
        self._client: Optional[ServiceBusClient] = None
        self._jobs_queue_name = settings.AZURE_SERVICE_BUS_QUEUE_NAME
        self._results_queue_name = settings.AZURE_SERVICE_BUS_RESULTS_QUEUE
        self._initialized = False
        self._init_client()

    def _init_client(self):
        conn_str = settings.AZURE_SERVICE_BUS_CONNECTION_STRING
        if not conn_str:
            logger.warning("[ServiceBus] AZURE_SERVICE_BUS_CONNECTION_STRING not configured. Running in local queue mode.")
            return

        try:
            self._client = ServiceBusClient.from_connection_string(
                conn_str,
                transport_type=TransportType.AmqpOverWebsocket
            )
            self._initialized = True
            logger.info(f"[ServiceBus] Connected to Service Bus via AmqpOverWebsocket for queues: '{self._jobs_queue_name}', '{self._results_queue_name}'")
        except Exception as e:
            logger.error(f"[ServiceBus] Connection failed: {e}")
            self._client = None

    @property
    def is_configured(self) -> bool:
        return self._initialized and (self._client is not None)

    def publish_job(self, job_id: str, file_name: str, blob_name: str, options: Optional[Dict[str, Any]] = None) -> bool:
        """
        Publishes a new document processing job to the Service Bus jobs queue with distributed trace context.
        """
        payload = {
            "job_id": job_id,
            "file_name": file_name,
            "blob_name": blob_name,
            "enqueued_at": time.time(),
            "options": options or {}
        }
        
        # Inject W3C trace context
        app_props = {"job_id": job_id, "file_name": file_name}
        inject_trace_context(app_props)

        with trace_span("azure.servicebus.publish_job", {"job_id": job_id, "queue": self._jobs_queue_name}):
            if self.is_configured:
                try:
                    with self._client.get_queue_sender(self._jobs_queue_name) as sender:
                        msg = ServiceBusMessage(
                            body=json.dumps(payload),
                            message_id=job_id,
                            correlation_id=job_id,
                            content_type="application/json",
                            application_properties=app_props
                        )
                        sender.send_messages(msg)
                        logger.info(f"[ServiceBus] Enqueued job {job_id} into '{self._jobs_queue_name}'")
                        return True
                except Exception as e:
                    logger.error(f"[ServiceBus] Failed to publish job {job_id}: {e}")
                    return False
            
            # Local fallback log
            logger.info(f"[ServiceBus:LocalFallback] Service Bus not configured. Job {job_id} requires fallback handling.")
            return False


    def publish_result(self, job_id: str, status: str, result_summary: Dict[str, Any]) -> bool:
        """
        Publishes processing result notification to the results queue.
        """
        payload = {
            "job_id": job_id,
            "status": status,
            "completed_at": time.time(),
            "summary": result_summary
        }
        with trace_span("azure.servicebus.publish_result", {"job_id": job_id, "status": status}):
            if self.is_configured:
                try:
                    with self._client.get_queue_sender(self._results_queue_name) as sender:
                        msg = ServiceBusMessage(
                            body=json.dumps(payload),
                            message_id=f"res-{job_id}",
                            correlation_id=job_id,
                            content_type="application/json"
                        )
                        sender.send_messages(msg)
                        logger.info(f"[ServiceBus] Published result for {job_id} into '{self._results_queue_name}'")
                        return True
                except Exception as e:
                    logger.warning(f"[ServiceBus] Failed to publish result for {job_id}: {e}")
            return True

    def get_queue_receiver(self, queue_name: Optional[str] = None) -> Optional[ServiceBusReceiver]:
        """Returns a ServiceBusReceiver for consumption loop."""
        if not self.is_configured:
            return None
        target_queue = queue_name or self._jobs_queue_name
        return self._client.get_queue_receiver(target_queue, max_wait_time=5)

    def get_queue_stats(self) -> Dict[str, Any]:
        """Queries queue lengths and dead-letter queue counts."""
        if not self.is_configured:
            return {
                "configured": False,
                "jobs_queue": 0,
                "results_queue": 0,
                "dead_letter_queue": 0
            }

        stats = {
            "configured": True,
            "jobs_queue": 0,
            "results_queue": 0,
            "dead_letter_queue": 0
        }
        try:
            with self._client.get_queue_receiver(self._jobs_queue_name, max_wait_time=2) as r1:
                msgs1 = r1.peek_messages(max_message_count=50)
                stats["jobs_queue"] = len(msgs1)
        except Exception as e:
            logger.warning(f"[ServiceBus] Error peeking {self._jobs_queue_name}: {e}")

        try:
            with self._client.get_queue_receiver(self._results_queue_name, max_wait_time=2) as r2:
                msgs2 = r2.peek_messages(max_message_count=50)
                stats["results_queue"] = len(msgs2)
        except Exception as e:
            logger.warning(f"[ServiceBus] Error peeking {self._results_queue_name}: {e}")

        try:
            from azure.servicebus import ServiceBusSubQueue
            with self._client.get_queue_receiver(self._jobs_queue_name, sub_queue=ServiceBusSubQueue.DEAD_LETTER, max_wait_time=2) as r3:
                msgs3 = r3.peek_messages(max_message_count=50)
                stats["dead_letter_queue"] = len(msgs3)
        except Exception as e:
            logger.warning(f"[ServiceBus] Error peeking DLQ for {self._jobs_queue_name}: {e}")

        return stats

    def flush_queues(self) -> Dict[str, Any]:
        """Drains and purges all waiting messages from jobs, results, and dead-letter queues."""
        if not self.is_configured:
            return {
                "status": "not_configured",
                "flushed_jobs": 0,
                "flushed_results": 0,
                "flushed_dead_letter": 0
            }

        flushed = {
            "status": "success",
            "flushed_jobs": 0,
            "flushed_results": 0,
            "flushed_dead_letter": 0
        }

        # 1. Drain jobs queue
        try:
            with self._client.get_queue_receiver(self._jobs_queue_name, max_wait_time=3) as receiver:
                while True:
                    msgs = receiver.receive_messages(max_message_count=20, max_wait_time=3)
                    if not msgs:
                        break
                    for m in msgs:
                        try:
                            receiver.complete_message(m)
                            flushed["flushed_jobs"] += 1
                        except Exception:
                            pass
        except Exception as e:
            logger.error(f"[ServiceBus] Error flushing jobs queue: {e}")

        # 2. Drain results queue
        try:
            with self._client.get_queue_receiver(self._results_queue_name, max_wait_time=3) as receiver:
                while True:
                    msgs = receiver.receive_messages(max_message_count=20, max_wait_time=3)
                    if not msgs:
                        break
                    for m in msgs:
                        try:
                            receiver.complete_message(m)
                            flushed["flushed_results"] += 1
                        except Exception:
                            pass
        except Exception as e:
            logger.error(f"[ServiceBus] Error flushing results queue: {e}")

        # 3. Drain dead letter queue
        try:
            from azure.servicebus import ServiceBusSubQueue
            with self._client.get_queue_receiver(self._jobs_queue_name, sub_queue=ServiceBusSubQueue.DEAD_LETTER, max_wait_time=3) as receiver:
                while True:
                    msgs = receiver.receive_messages(max_message_count=20, max_wait_time=3)
                    if not msgs:
                        break
                    for m in msgs:
                        try:
                            receiver.complete_message(m)
                            flushed["flushed_dead_letter"] += 1
                        except Exception:
                            pass
        except Exception as e:
            logger.error(f"[ServiceBus] Error flushing DLQ: {e}")

        logger.info(f"[ServiceBus] Flushed queues: {flushed}")
        return flushed

# Singleton Service Bus client
service_bus_service = AzureServiceBusService()


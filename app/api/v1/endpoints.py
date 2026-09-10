import io
import json
import uuid
import asyncio
import time
import requests
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse, Response, StreamingResponse

from app.models.schema import DocumentAnalysisResult, ElementCategory, TranslationRequest, TranslationResponse
from app.services.azure_doc_intel import AzureDocIntelService
from app.services.azure_storage import storage_service
from app.services.azure_service_bus import service_bus_service
from app.services.azure_translator import translator_service, SUPPORTED_LANGUAGES
from app.services.telemetry import trace_span
from app.services.sample_generator import get_sample_document, build_sample_expense_report, build_sample_financial_report
from app.database.store import save_document_to_db, get_document_from_db, list_recent_documents_from_db, update_document_element_in_db
from app.database.job_store import create_job, get_job, get_job_result, list_recent_jobs
from app.worker.processor import worker_instance
from app.config import settings

router = APIRouter()

doc_intel_service = AzureDocIntelService()

# In-memory document storage cache for demo/active sessions
DOCUMENT_CACHE: Dict[str, DocumentAnalysisResult] = {
    "sample-expense-001": build_sample_expense_report(),
    "sample-financial-002": build_sample_financial_report()
}

@router.get("/health")
async def health_check():
    """Enterprise health check endpoint and Azure Cloud Service configuration status."""
    return {
        "status": "online",
        "version": settings.VERSION,
        "environment": "azure-fde-production",
        "azure_doc_intel_configured": doc_intel_service.is_configured,
        "azure_translator_configured": translator_service.is_configured,
        "azure_openai_configured": bool(settings.AZURE_OPENAI_ENDPOINT and settings.AZURE_OPENAI_KEY),
        "azure_service_bus_configured": service_bus_service.is_configured,
        "azure_storage_configured": storage_service.is_configured,
        "application_insights_configured": bool(settings.APPLICATIONINSIGHTS_CONNECTION_STRING),
        "async_worker_enabled": settings.ENABLE_ASYNC_WORKER,
        "max_concurrent_users_limit": settings.MAX_CONCURRENT_USERS,
        "demo_mode": settings.DEMO_MODE
    }

@router.post("/translate", response_model=TranslationResponse)
async def translate_text_endpoint(req: TranslationRequest):
    """
    Azure AI Translator Endpoint:
    Translates extracted text into one of 5 supported languages:
    Hindi ('hi'), Telugu ('te'), French ('fr'), German ('de'), Kannada ('kn').
    """
    try:
        res = translator_service.translate_text(
            text=req.text,
            target_language=req.target_language,
            source_language=req.source_language or "en"
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/documents/{doc_id}/elements/{element_id}")
async def update_element_text(doc_id: str, element_id: str, payload: Dict[str, Any]):
    """
    Updates the extracted text content or structured data (table_data, key_value_pair, chart_summary)
    of a specific element in active cache and SQLite database.
    """
    new_text = payload.get("text_content")
    table_data = payload.get("table_data")
    kv_pair = payload.get("key_value_pair")
    chart_summary = payload.get("chart_summary")

    # Update cache if available
    if doc_id in DOCUMENT_CACHE:
        doc = DOCUMENT_CACHE[doc_id]
        for page in doc.pages:
            for elem in page.elements:
                if elem.id == element_id:
                    if new_text is not None:
                        elem.text_content = new_text
                    if table_data is not None and elem.table_data:
                        if isinstance(table_data, dict):
                            elem.table_data.markdown_table = table_data.get("markdown_table", elem.table_data.markdown_table)
                    if kv_pair is not None:
                        elem.key_value_pair = kv_pair
                    if chart_summary is not None:
                        elem.chart_summary = chart_summary
                    break

    # Persist in SQLite DB
    update_document_element_in_db(doc_id, element_id, payload)
    return {"status": "success", "document_id": doc_id, "element_id": element_id, "payload": payload}



# ==========================================
# ENTERPRISE ASYNC SERVICE BUS JOB PIPELINE
# ==========================================

@router.post("/jobs/submit", status_code=202)
async def submit_async_job(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    Enterprise FDE Ingestion:
    Streams file into Azure Blob Storage, publishes processing job to Azure Service Bus,
    and returns HTTP 202 Accepted with tracking job ID.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB")

    job_id = f"job-{uuid.uuid4().hex[:12]}"
    
    # 1. Upload to Azure Blob Storage
    blob_name, blob_url = storage_service.upload_document(content, file.filename, job_id)

    # 2. Record Job in Enterprise Store
    job_record = create_job(job_id, file.filename, len(content), blob_name)

    # 3. Publish to Azure Service Bus Queue
    published = service_bus_service.publish_job(
        job_id=job_id,
        file_name=file.filename,
        blob_name=blob_name,
        options={"blob_url": blob_url}
    )

    if not published:
        # Fallback to in-process background worker execution if Service Bus is not available
        background_tasks.add_task(worker_instance.process_job_direct, job_id, file.filename, blob_name, content)

    return {
        "job_id": job_id,
        "status": "QUEUED",
        "file_name": file.filename,
        "file_size_bytes": len(content),
        "blob_name": blob_name,
        "queue_name": settings.AZURE_SERVICE_BUS_QUEUE_NAME,
        "status_url": f"/api/v1/jobs/{job_id}/status",
        "stream_url": f"/api/v1/jobs/{job_id}/stream",
        "result_url": f"/api/v1/jobs/{job_id}/result",
        "enqueued_at": job_record.get("enqueued_at")
    }

@router.get("/jobs/{job_id}/status")
async def get_job_status(job_id: str):
    """Returns the current state and stage progression of an asynchronous job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job

@router.get("/jobs/{job_id}/result")
async def get_async_job_result(job_id: str):
    """Retrieves the completed DocumentAnalysisResult for an async job."""
    res = get_job_result(job_id)
    if res:
        return res
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    if job.get("status") == "FAILED":
        raise HTTPException(status_code=500, detail=f"Job failed: {job.get('error_message')}")
    return JSONResponse(status_code=202, content={"status": job.get("status"), "current_stage": job.get("current_stage"), "progress_pct": job.get("progress_pct")})

@router.get("/jobs/{job_id}/stream")
async def stream_job_progress(job_id: str):
    """
    Server-Sent Events (SSE) endpoint providing real-time live progression events
    for UI visualization of the Azure Service Bus worker pipeline.
    """
    async def event_generator():
        for _ in range(150):  # Maximum 150 seconds wait
            job = get_job(job_id)
            if not job:
                yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                break

            status = job.get("status")
            yield f"data: {json.dumps(job)}\n\n"

            if status in ("COMPLETED", "FAILED"):
                break

            await asyncio.sleep(0.8)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/jobs/recent")
async def list_recent_async_jobs(limit: int = 15):
    """Returns recent asynchronous jobs processed by the Azure Service Bus worker."""
    return list_recent_jobs(limit)

# ==========================================
# INTERACTIVE / SYNCHRONOUS CORE ENDPOINTS
# ==========================================

@router.get("/documents/samples")
async def list_sample_documents():
    """Returns list of pre-packaged sample documents for instant UI exploration."""
    return [
        {
            "id": "sample-expense-001",
            "title": "Expense & Travel Invoice (Tables, KV-Pairs, Approval)",
            "description": "Multi-category document with itemized travel expenses, category breakdown donut chart, and approval key-values.",
            "pages": 1,
            "elements_count": 5
        },
        {
            "id": "sample-financial-002",
            "title": "Financial Forecast Report (Revenue Bar Chart, Architecture Diagram, Profitability Table)",
            "description": "Enterprise performance report with quarterly revenue bar charts, cloud architecture diagram, and segment breakdown table.",
            "pages": 1,
            "elements_count": 4
        }
    ]

@router.get("/documents/history")
async def get_document_history():
    """Returns list of all previously uploaded and analyzed documents stored in SQLite database."""
    return list_recent_documents_from_db(30)

@router.get("/documents/{doc_id}", response_model=DocumentAnalysisResult)
async def get_document_by_id(doc_id: str):
    """Fetch structured document analysis by ID from cache or SQLite database."""
    if doc_id in DOCUMENT_CACHE:
        return DOCUMENT_CACHE[doc_id]
    
    db_doc = get_document_from_db(doc_id)
    if db_doc:
        doc_obj = DocumentAnalysisResult(**db_doc)
        DOCUMENT_CACHE[doc_id] = doc_obj
        return doc_obj

    raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")

@router.post("/documents/upload", response_model=DocumentAnalysisResult)
async def upload_document(file: UploadFile = File(...)):
    """Interactive/Synchronous: Uploads a file, runs Azure AI analysis immediately, saves to DB, and returns result."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB")

    # Also persist to Blob Storage asynchronously
    try:
        storage_service.upload_document(content, file.filename, f"sync-{int(time.time())}")
    except Exception:
        pass

    result = doc_intel_service.analyze_document_bytes(content, file.filename)
    DOCUMENT_CACHE[result.document_id] = result
    
    # Save to SQLite database for future retrieval
    save_document_to_db(result.document_id, result.file_name, len(content), "upload", result.model_dump())
    return result

@router.post("/documents/url", response_model=DocumentAnalysisResult)
async def process_document_url(url: str = Form(...)):
    """Fetches a document from an external URL, analyzes layout, saves to DB, and returns result."""
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        filename = url.split("/")[-1] or "remote_document.pdf"
        result = doc_intel_service.analyze_document_bytes(resp.content, filename)
        result.source_type = "url"
        DOCUMENT_CACHE[result.document_id] = result
        
        # Save to SQLite database for future retrieval
        save_document_to_db(result.document_id, filename, len(resp.content), "url", result.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to download document from URL: {str(e)}")

@router.get("/documents/{doc_id}/export/{format_type}")
async def export_document_data(doc_id: str, format_type: str = "json"):
    """Export extracted document elements into CSV or JSON format."""
    if doc_id in DOCUMENT_CACHE:
        doc = DOCUMENT_CACHE[doc_id]
    else:
        db_doc = get_document_from_db(doc_id)
        if not db_doc:
            raise HTTPException(status_code=404, detail="Document not found")
        doc = DocumentAnalysisResult(**db_doc)

    if format_type.lower() == "csv":
        csv_chunks = []
        for page in doc.pages:
            for elem in page.elements:
                if elem.table_data:
                    csv_chunks.append(f"--- Table: {elem.label} (Page {elem.page_number}) ---\n" + elem.table_data.csv_content)
        
        full_csv = "\n\n".join(csv_chunks) if csv_chunks else "No tabular data found in document."
        return Response(content=full_csv, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={doc_id}_tables.csv"})

    return JSONResponse(content=doc.dict() if hasattr(doc, "dict") else doc.model_dump())

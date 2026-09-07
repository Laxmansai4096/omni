"""
Enterprise Job Store for Asynchronous Processing
Tracks job lifecycle states: QUEUED -> FETCHING -> EXTRACTING_OCR -> ANALYZING_VISION -> COMPLETED / FAILED.
"""

import sqlite3
import json
import time
import os
from typing import Optional, Dict, Any, List

DB_PATH = os.path.join(os.path.dirname(__file__), "omnidoc_store.db")

def init_job_table():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS async_jobs (
            job_id TEXT PRIMARY KEY,
            file_name TEXT NOT NULL,
            file_size_bytes INTEGER DEFAULT 0,
            blob_name TEXT,
            status TEXT NOT NULL,
            progress_pct INTEGER DEFAULT 0,
            current_stage TEXT DEFAULT 'QUEUED',
            enqueued_at REAL,
            started_at REAL,
            completed_at REAL,
            error_message TEXT,
            result_json TEXT
        )
    """)
    conn.commit()
    conn.close()

def create_job(job_id: str, file_name: str, file_size_bytes: int, blob_name: str) -> Dict[str, Any]:
    init_job_table()
    now = time.time()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO async_jobs 
        (job_id, file_name, file_size_bytes, blob_name, status, progress_pct, current_stage, enqueued_at)
        VALUES (?, ?, ?, ?, 'QUEUED', 5, 'QUEUED_IN_SERVICE_BUS', ?)
    """, (job_id, file_name, file_size_bytes, blob_name, now))
    conn.commit()
    conn.close()
    return get_job(job_id)

def update_job_stage(job_id: str, status: str, progress_pct: int, current_stage: str, error_message: Optional[str] = None):
    init_job_table()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = time.time()
    if status == "PROCESSING" and progress_pct <= 20:
        cursor.execute("""
            UPDATE async_jobs
            SET status = ?, progress_pct = ?, current_stage = ?, started_at = COALESCE(started_at, ?), error_message = ?
            WHERE job_id = ?
        """, (status, progress_pct, current_stage, now, error_message, job_id))
    elif status in ("COMPLETED", "FAILED"):
        cursor.execute("""
            UPDATE async_jobs
            SET status = ?, progress_pct = ?, current_stage = ?, completed_at = ?, error_message = ?
            WHERE job_id = ?
        """, (status, progress_pct, current_stage, now, error_message, job_id))
    else:
        cursor.execute("""
            UPDATE async_jobs
            SET status = ?, progress_pct = ?, current_stage = ?, error_message = ?
            WHERE job_id = ?
        """, (status, progress_pct, current_stage, error_message, job_id))
    conn.commit()
    conn.close()

def save_job_result(job_id: str, result_dict: Dict[str, Any]):
    init_job_table()
    now = time.time()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE async_jobs
        SET status = 'COMPLETED', progress_pct = 100, current_stage = 'PROCESSING_COMPLETED', completed_at = ?, result_json = ?
        WHERE job_id = ?
    """, (now, json.dumps(result_dict), job_id))
    conn.commit()
    conn.close()

def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    init_job_table()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT job_id, file_name, file_size_bytes, blob_name, status, progress_pct, current_stage,
               enqueued_at, started_at, completed_at, error_message, result_json
        FROM async_jobs WHERE job_id = ?
    """, (job_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "job_id": row[0],
        "file_name": row[1],
        "file_size_bytes": row[2],
        "blob_name": row[3],
        "status": row[4],
        "progress_pct": row[5],
        "current_stage": row[6],
        "enqueued_at": row[7],
        "started_at": row[8],
        "completed_at": row[9],
        "error_message": row[10],
        "has_result": row[11] is not None
    }

def get_job_result(job_id: str) -> Optional[Dict[str, Any]]:
    init_job_table()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT result_json FROM async_jobs WHERE job_id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        return json.loads(row[0])
    return None

def list_recent_jobs(limit: int = 15) -> List[Dict[str, Any]]:
    init_job_table()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT job_id, file_name, file_size_bytes, status, progress_pct, current_stage, enqueued_at, completed_at
        FROM async_jobs ORDER BY enqueued_at DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "job_id": r[0],
            "file_name": r[1],
            "file_size_bytes": r[2],
            "status": r[3],
            "progress_pct": r[4],
            "current_stage": r[5],
            "enqueued_at": r[6],
            "completed_at": r[7]
        }
        for r in rows
    ]

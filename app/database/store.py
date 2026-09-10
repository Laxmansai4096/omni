import sqlite3
import json
import time
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "omnidoc_store.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            document_id TEXT PRIMARY KEY,
            file_name TEXT NOT NULL,
            file_size_bytes INTEGER,
            source_type TEXT,
            created_at REAL,
            json_data TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def save_document_to_db(doc_id: str, file_name: str, file_size: int, source_type: str, result_dict: dict):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO documents (document_id, file_name, file_size_bytes, source_type, created_at, json_data)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (doc_id, file_name, file_size, source_type, time.time(), json.dumps(result_dict)))
    conn.commit()
    conn.close()

def get_document_from_db(doc_id: str) -> dict:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT json_data FROM documents WHERE document_id = ?", (doc_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None

def list_recent_documents_from_db(limit: int = 20) -> list:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT document_id, file_name, file_size_bytes, source_type, created_at
        FROM documents ORDER BY created_at DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    res = []
    for r in rows:
        res.append({
            "document_id": r[0],
            "file_name": r[1],
            "file_size_bytes": r[2],
            "source_type": r[3],
            "created_at": r[4]
        })
    return res

def update_document_element_in_db(doc_id: str, element_id: str, payload: dict) -> bool:
    doc = get_document_from_db(doc_id)
    if not doc:
        return False
    
    updated = False
    new_text = payload.get("text_content")
    table_data = payload.get("table_data")
    kv_pair = payload.get("key_value_pair")
    chart_summary = payload.get("chart_summary")

    for page in doc.get("pages", []):
        for elem in page.get("elements", []):
            if elem.get("id") == element_id:
                if new_text is not None:
                    elem["text_content"] = new_text
                if table_data is not None:
                    elem["table_data"] = table_data
                if kv_pair is not None:
                    elem["key_value_pair"] = kv_pair
                if chart_summary is not None:
                    elem["chart_summary"] = chart_summary
                updated = True
                break

    if updated:
        save_document_to_db(doc_id, doc.get("file_name", "document.png"), doc.get("file_size_bytes", 0), doc.get("source_type", "upload"), doc)
    return updated


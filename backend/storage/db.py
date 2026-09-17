import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from backend.config import settings

def get_connection():
    conn = sqlite3.connect(str(settings.db_path))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        created_at TEXT,
        video_path TEXT,
        video_name TEXT,
        video_duration REAL DEFAULT 0,
        target_agent TEXT,
        target_username TEXT,
        status TEXT DEFAULT 'QUEUED',
        stage TEXT DEFAULT 'Initialized',
        progress REAL DEFAULT 0,
        candidate_count INTEGER DEFAULT 0,
        encounter_count INTEGER DEFAULT 0,
        target_encounter_count INTEGER DEFAULT 0,
        ignored_encounter_count INTEGER DEFAULT 0,
        error_message TEXT,
        settings_json TEXT,
        report_json TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS encounters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT,
        encounter_index INTEGER,
        start_sec REAL,
        event_sec REAL,
        end_sec REAL,
        clip_path TEXT,
        target_agent TEXT,
        detected_agent TEXT,
        is_target_player BOOLEAN,
        player_state TEXT,
        event_valid BOOLEAN,
        event_type TEXT,
        result TEXT,
        mistake_severity TEXT,
        avoidable BOOLEAN,
        confidence REAL,
        analysis_json TEXT,
        FOREIGN KEY(job_id) REFERENCES jobs(id)
    );
    """)
    conn.commit()
    conn.close()

def create_job(job_id: str, video_path: str, video_name: str, target_agent: str, target_username: str, job_settings: dict) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT INTO jobs (id, created_at, video_path, video_name, target_agent, target_username, settings_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (job_id, now, video_path, video_name, target_agent, target_username, json.dumps(job_settings)))
    conn.commit()
    conn.close()
    return get_job(job_id)

def update_job(job_id: str, **kwargs):
    conn = get_connection()
    cursor = conn.cursor()
    fields = []
    values = []
    for k, v in kwargs.items():
        col_name = k
        if k == "report":
            col_name = "report_json"
        elif k == "settings":
            col_name = "settings_json"

        fields.append(f"{col_name} = ?")
        if isinstance(v, (dict, list)):
            values.append(json.dumps(v))
        else:
            values.append(v)
    values.append(job_id)
    query = f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?"
    cursor.execute(query, values)
    conn.commit()
    conn.close()

def get_job(job_id: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    res = dict(row)
    if res.get('settings_json'):
        res['settings'] = json.loads(res['settings_json'])
    if res.get('report_json'):
        res['report'] = json.loads(res['report_json'])
    return res

def list_jobs(limit: int = 50) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    jobs = []
    for r in rows:
        d = dict(r)
        if d.get('settings_json'):
            d['settings'] = json.loads(d['settings_json'])
        if d.get('report_json'):
            d['report'] = json.loads(d['report_json'])
        jobs.append(d)
    return jobs

def save_encounters(job_id: str, encounters: List[dict]):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM encounters WHERE job_id = ?", (job_id,))
    for e in encounters:
        cursor.execute("""
            INSERT INTO encounters (
                job_id, encounter_index, start_sec, event_sec, end_sec, clip_path,
                target_agent, detected_agent, is_target_player, player_state,
                event_valid, event_type, result, mistake_severity, avoidable,
                confidence, analysis_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id, e.get('encounter_index', 0), e.get('start_sec', 0.0), e.get('event_sec', 0.0),
            e.get('end_sec', 0.0), e.get('clip_path', ''), e.get('target_agent', ''),
            e.get('detected_agent', ''), bool(e.get('is_target_player', False)),
            e.get('player_state', 'UNKNOWN'), bool(e.get('event_valid', False)),
            e.get('event_type', 'UNKNOWN'), e.get('result', 'UNKNOWN'),
            e.get('mistake_severity', 'LOW'), bool(e.get('avoidable', False)),
            e.get('confidence', 0.0), json.dumps(e)
        ))
    conn.commit()
    conn.close()

def get_encounters(job_id: str, target_only: bool = False) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    if target_only:
        cursor.execute("SELECT * FROM encounters WHERE job_id = ? AND is_target_player = 1 ORDER BY encounter_index ASC", (job_id,))
    else:
        cursor.execute("SELECT * FROM encounters WHERE job_id = ? ORDER BY encounter_index ASC", (job_id,))
    rows = cursor.fetchall()
    conn.close()
    encounters = []
    for r in rows:
        d = dict(r)
        if d.get('analysis_json'):
            parsed = json.loads(d['analysis_json'])
            d.update(parsed)
        encounters.append(d)
    return encounters

init_db()

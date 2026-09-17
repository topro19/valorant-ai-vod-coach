import os
import uuid
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import settings
from backend.storage.db import (
    create_job, get_job, list_jobs, update_job, get_encounters
)
from backend.analysis.engine import AnalysisEngine

app = FastAPI(title="VALORANT AI VOD COACH", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

class AnalysisRequest(BaseModel):
    video_path: str
    video_name: Optional[str] = None
    target_agent: str
    target_username: Optional[str] = ""
    merge_window: Optional[float] = 7.0
    pre_roll: Optional[float] = 12.0
    post_roll: Optional[float] = 5.0
    gemini_model: Optional[str] = "gemini-2.5-flash"
    analysis_depth: Optional[str] = "standard"

class SettingsUpdateRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    data_dir: Optional[str] = None

class VerifyKeyRequest(BaseModel):
    gemini_api_key: str

def run_analysis_task(job_id: str):
    engine = AnalysisEngine(job_id)
    engine.run()

@app.get("/api/health")
def health():
    return {"status": "ok", "app": "VALORANT AI VOD COACH"}

@app.get("/api/local-captures")
def list_local_captures():
    user_home = Path.home()
    captures_dir = user_home / "Videos" / "Captures"
    files_list = []
    if captures_dir.exists():
        for f in captures_dir.glob("*.mp4"):
            try:
                stat = f.stat()
                files_list.append({
                    "name": f.name,
                    "path": str(f),
                    "size_mb": round(stat.st_size / (1024 * 1024), 1),
                    "modified": stat.st_mtime
                })
            except Exception:
                pass
    files_list = sorted(files_list, key=lambda x: x["modified"], reverse=True)
    return {"captures": files_list}

@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in [".mp4", ".mkv", ".mov", ".webm"]:
        raise HTTPException(status_code=400, detail="Unsupported video format. Please upload MP4, MKV, MOV, or WEBM.")

    unique_name = f"{uuid.uuid4().hex}_{file.filename}"
    target_path = settings.uploads_dir / unique_name

    with open(target_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024 * 10):
            buffer.write(chunk)

    return {
        "status": "uploaded",
        "video_path": str(target_path),
        "video_name": file.filename,
        "size_bytes": os.path.getsize(target_path)
    }

@app.post("/api/analyze")
def start_analysis(req: AnalysisRequest, background_tasks: BackgroundTasks):
    if not os.path.exists(req.video_path):
        raise HTTPException(status_code=404, detail=f"Video file not found at: {req.video_path}")
    if not req.target_agent:
        raise HTTPException(status_code=400, detail="Target agent is required for the Player Lock system.")

    job_id = uuid.uuid4().hex[:12]
    video_name = req.video_name or os.path.basename(req.video_path)

    job_settings = {
        "merge_window": req.merge_window,
        "pre_roll": req.pre_roll,
        "post_roll": req.post_roll,
        "gemini_model": req.gemini_model,
        "analysis_depth": req.analysis_depth
    }

    create_job(
        job_id=job_id,
        video_path=req.video_path,
        video_name=video_name,
        target_agent=req.target_agent,
        target_username=req.target_username or "",
        job_settings=job_settings
    )

    background_tasks.add_task(run_analysis_task, job_id)

    return {"status": "started", "job_id": job_id}

@app.get("/api/jobs")
def get_recent_jobs():
    return {"jobs": list_jobs()}

@app.get("/api/jobs/{job_id}")
def get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.get("/api/jobs/{job_id}/encounters")
def get_job_encounters(job_id: str, target_only: bool = False):
    encs = get_encounters(job_id, target_only=target_only)
    return {"encounters": encs}

@app.get("/api/jobs/{job_id}/report")
def get_job_report(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") != "COMPLETED":
        return {"status": job.get("status"), "report": None, "stage": job.get("stage")}
    return {"status": "COMPLETED", "report": job.get("report")}

@app.get("/api/clips/{job_id}/{filename}")
def stream_clip(job_id: str, filename: str):
    file_path = settings.clips_dir / job_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Clip file not found")
    media_type = "video/mp4" if filename.endswith(".mp4") else "image/jpeg"
    return FileResponse(file_path, media_type=media_type)

@app.get("/api/settings")
def get_current_settings():
    has_key = bool(settings.gemini_api_key)
    masked_key = (settings.gemini_api_key[:6] + "..." + settings.gemini_api_key[-4:]) if len(settings.gemini_api_key) > 10 else ("***" if has_key else "")
    return {
        "has_gemini_key": has_key,
        "masked_key": masked_key,
        "gemini_model": settings.gemini_model,
        "data_dir": str(settings.data_dir),
        "host": settings.host,
        "port": settings.port
    }

@app.post("/api/verify-key")
def verify_gemini_key(req: VerifyKeyRequest):
    """
    Tests and saves the user's Gemini API key live.
    """
    key = req.gemini_api_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="API key cannot be empty.")

    try:
        from google import genai
        client = genai.Client(api_key=key)
        res = client.models.generate_content(
            model=settings.gemini_model,
            contents="Hello"
        )
        settings.update_setting("GEMINI_API_KEY", key)
        masked = (key[:6] + "..." + key[-4:]) if len(key) > 10 else "***"
        return {"valid": True, "masked_key": masked, "message": "Gemini API key successfully verified and saved!"}
    except Exception as e:
        return {"valid": False, "error": str(e), "message": f"Verification failed: {str(e)}"}

@app.post("/api/settings")
def update_app_settings(req: SettingsUpdateRequest):
    if req.gemini_api_key is not None:
        settings.update_setting("GEMINI_API_KEY", req.gemini_api_key.strip())
    if req.gemini_model is not None:
        settings.update_setting("GEMINI_MODEL", req.gemini_model.strip())
    if req.data_dir is not None:
        settings.update_setting("DATA_DIR", req.data_dir.strip())
    return {"status": "updated"}

# Serve frontend static assets
app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")

@app.get("/{full_path:path}")
def serve_frontend(full_path: str):
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse({"message": "Frontend not built yet"})

import os
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_ZIP = BASE_DIR.parent / "VALORANT_AI_VOD_COACH_Setup.zip"

EXCLUDE_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "data", "temp"}
EXCLUDE_EXTS = {".pyc", ".pyo", ".mp4", ".mkv", ".mov", ".zip"}
EXCLUDE_FILES = {".env", "transcript.jsonl", "transcript_full.jsonl"}

def should_include(rel_path: Path) -> bool:
    for part in rel_path.parts:
        if part in EXCLUDE_DIRS:
            return False
    if rel_path.name in EXCLUDE_FILES:
        return False
    if rel_path.suffix.lower() in EXCLUDE_EXTS:
        return False
    return True

def create_package():
    print(f"Bundling shareable package from: {BASE_DIR}")
    print(f"Target Zip File: {OUTPUT_ZIP}")
    
    total_files = 0
    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(BASE_DIR):
            # Prune excluded directories
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            
            for file in files:
                full_path = Path(root) / file
                rel_path = full_path.relative_to(BASE_DIR)
                
                if should_include(rel_path):
                    # Store under a clean root folder inside the zip
                    arcname = Path("VALORANT-AI-VOD-COACH") / rel_path
                    zf.write(full_path, arcname)
                    total_files += 1

    size_mb = OUTPUT_ZIP.stat().st_size / (1024 * 1024)
    print("=" * 60)
    print(f"[SUCCESS] Shareable package created successfully!")
    print(f"Path : {OUTPUT_ZIP}")
    print(f"Files: {total_files}")
    print(f"Size : {size_mb:.2f} MB")
    print("=" * 60)
    print("You can send this zip file directly to your friends!")

if __name__ == "__main__":
    create_package()

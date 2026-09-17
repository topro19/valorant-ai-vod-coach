# VALORANT AI VOD COACH

A specialized Windows web application for competitive Valorant players. It analyzes gameplay recordings using OpenCV-based event detection and Gemini video intelligence with a **strict Player Lock system**.

---

## 🎯 Core Feature: Strict Player Lock

Standard video coaches often confuse spectator camera footage with user gameplay. When you die and the camera switches to spectate a teammate (e.g. Phoenix, Reyna), generic analyzers mistakenly give you advice based on your teammate's actions.

**VALORANT AI VOD COACH eliminates this problem:**
- **Level 1 Configuration:** Set your Agent (`Breach`, `Jett`, `Cypher`, etc.) and optional Riot Username.
- **Level 2 Visual Verification:** Independently verifies the HUD, ability icons, first-person hands/weapons, and spectator labels.
- **State Machine:**
  ```
  USER_ALIVE (Analyze Gameplay)
      ↓ Player dies
  USER_DIED (Analyze Death)
      ↓ Camera switches
  SPECTATING_TEAMMATE (IGNORE ENTIRELY — Zero advice generated)
      ↓ Next round
  USER_ALIVE (Resume analysis only after visual confirmation)
  ```
- **Guaranteed Result:** Zero advice is ever derived from teammate or spectator footage.

---

## 🚀 Quick Start

### 1. Requirements
- Windows 10/11
- Python 3.10+
- FFmpeg installed and accessible in `PATH`

### 2. Launch as Native Windows Desktop App
You can launch the app directly:
- **Desktop Shortcut:** Double-click `VALORANT AI VOD Coach` on your Windows Desktop.
- **Batch Launcher:** Double-click `Launch Coach.bat` in the project directory.
- **Terminal:** Run:
  ```bash
  python app.py
  ```
This starts the backend and opens a standalone tactical window (powered by pywebview and Edge Chromium) with zero browser chrome or toolbars.

*(Alternatively, run `python run.py` to host in standard browser mode at `http://127.0.0.1:8000`).*

---

## 📁 File Storage
All data is stored locally in `D:\`:
- **Folder:** `D:\valorant-vod-coach-data\`
  - `/uploads`: Uploaded VOD recordings
  - `/clips`: Extracted encounter video clips for HTML5 streaming
  - `/reports`: Post-match coaching reports
  - `/db`: SQLite database (`vod_coach.db`)

---

## 🔑 Gemini API Key Configuration
You can enter your Google Gemini API key directly in the application:
1. **First-Launch Setup Modal:** The app prompts you to connect your key on first startup.
2. **Instant Verification:** Click **VERIFY & ACTIVATE KEY** to test live against Google Gemini 2.5 Flash.
3. **Settings & Status:** Click the API status badge in the sidebar or go to **Settings** anytime to test, change, or mask your key.
4. **Offline / Demo Mode:** You can skip key configuration at any time to run in local deterministic mode.
*(Your key is saved locally in `.env` and is strictly git-ignored to prevent accidental exposure).*

---

## 🧪 Testing
To run the automated critical acceptance test suite:
```bash
python -m unittest tests.test_acceptance_scenario
```

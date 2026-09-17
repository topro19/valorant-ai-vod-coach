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

### 2. Run the Application
In your terminal, navigate to the project folder and run:
```bash
python run.py
```
Open your browser at:
```
http://127.0.0.1:8000
```

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
You can configure your `GEMINI_API_KEY` in two ways:
1. Inside the Web UI: Go to **Settings** → Paste your Gemini API key → Click **Save Configuration**.
2. Inside `.env`: Edit `d:\uwu\valorant-vod-coach\.env`:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ```
*(Note: If no API key is provided, the application runs in local deterministic verification mode so you can test all features without interruption).*

---

## 🧪 Testing
To run the automated critical acceptance test suite:
```bash
python -m unittest tests.test_acceptance_scenario
```

import os
import sys
import shutil
import zipfile
import subprocess
import urllib.request
from pathlib import Path

GITHUB_REPO_ZIP = "https://github.com/topro19/valorant-ai-vod-coach/archive/refs/heads/master.zip"

def print_banner():
    print("=" * 70)
    print("            VALORANT AI VOD COACH - 1-FILE INSTALLER")
    print("=" * 70)
    print("This script will set up the entire application, install all dependencies,")
    print("create a Desktop shortcut, and launch your tactical AI coach.")
    print("=" * 70)
    print()

def main():
    print_banner()

    # 1. Determine destination folder
    current_dir = Path(__file__).resolve().parent
    # If this setup.py is already inside the project folder
    if (current_dir / "backend").exists() and (current_dir / "frontend").exists():
        target_dir = current_dir
        print(f"[1/5] Running inside existing application folder: {target_dir}")
    else:
        # Standalone: User just ran setup.py in Downloads or an empty folder
        target_dir = current_dir / "ValorantVodCoach"
        target_dir.mkdir(parents=True, exist_ok=True)
        print(f"[1/5] Installing application to: {target_dir}")
        print("Downloading latest application files from GitHub...")
        
        zip_path = target_dir / "repo_temp.zip"
        try:
            req = urllib.request.Request(GITHUB_REPO_ZIP, headers={"User-Agent": "VodCoachInstaller/1.0"})
            with urllib.request.urlopen(req) as resp, open(zip_path, "wb") as out_f:
                shutil.copyfileobj(resp, out_f)
            
            print("Extracting files...")
            with zipfile.ZipFile(zip_path, "r") as zf:
                for member in zf.namelist():
                    # GitHub zips put files inside 'valorant-ai-vod-coach-master/...'
                    parts = Path(member).parts
                    if len(parts) > 1:
                        subpath = Path(*parts[1:])
                        dest = target_dir / subpath
                        if member.endswith("/"):
                            dest.mkdir(parents=True, exist_ok=True)
                        else:
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            with zf.open(member) as src, open(dest, "wb") as dst:
                                shutil.copyfileobj(src, dst)
            
            if zip_path.exists():
                zip_path.unlink()
            print("[OK] Latest application files downloaded and extracted.")
        except Exception as e:
            print(f"[!] Error downloading files from GitHub: {e}")
            print("Please check your internet connection.")
            input("\nPress Enter to exit...")
            sys.exit(1)

    # 2. Initialize configuration (.env)
    print("\n[2/5] Initializing local configuration (.env)...")
    env_file = target_dir / ".env"
    env_example = target_dir / ".env.example"
    if not env_file.exists():
        if env_example.exists():
            shutil.copy(env_example, env_file)
            print("[OK] Created .env from template.")
        else:
            with open(env_file, "w") as f:
                f.write("GEMINI_API_KEY=\nDATA_DIR=\n")
            print("[OK] Created default .env.")
    else:
        print("[OK] Existing configuration found.")

    # 3. Setup Virtual Environment
    print("\n[3/5] Setting up isolated Python virtual environment (.venv)...")
    venv_dir = target_dir / ".venv"
    python_exe = venv_dir / "Scripts" / "python.exe"
    
    if not python_exe.exists():
        print("Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        print("[OK] Virtual environment created successfully.")
    else:
        print("[OK] Virtual environment already exists.")

    # 4. Install Dependencies
    print("\n[4/5] Installing required packages (FastAPI, OpenCV, PyWebView, Gemini SDK)...")
    req_file = target_dir / "requirements.txt"
    if req_file.exists():
        subprocess.run([str(python_exe), "-m", "pip", "install", "--upgrade", "pip", "--quiet"], check=False)
        res = subprocess.run([str(python_exe), "-m", "pip", "install", "-r", str(req_file)], check=False)
        if res.returncode == 0:
            print("[OK] All packages installed successfully.")
        else:
            print("[!] Warning: Some packages had installation warnings.")

    # Check FFmpeg
    ffmpeg_available = shutil.which("ffmpeg") is not None or (target_dir / "bin" / "ffmpeg.exe").exists()
    if ffmpeg_available:
        print("[OK] FFmpeg is available.")
    else:
        print("[!] Note: FFmpeg was not detected. You can install it via 'winget install Gyan.FFmpeg' or let the coach run in standard mode.")

    # 5. Create Desktop Shortcut
    print("\n[5/5] Creating Windows Desktop Shortcut...")
    try:
        desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
        if desktop.exists():
            shortcut_script = f"""
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut('{str(desktop / "VALORANT AI VOD Coach.lnk")}')
$shortcut.TargetPath = '{str(target_dir / "Launch Coach.bat")}'
$shortcut.WorkingDirectory = '{str(target_dir)}'
$shortcut.Description = 'VALORANT AI VOD Coach'
$shortcut.Save()
"""
            subprocess.run(["powershell", "-Command", shortcut_script], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"[OK] Desktop shortcut created at: {desktop / 'VALORANT AI VOD Coach.lnk'}")
    except Exception as e:
        print(f"[!] Could not create desktop shortcut: {e}")

    print("\n" + "=" * 70)
    print("                    SETUP COMPLETED SUCCESSFULLY!")
    print("=" * 70)
    print(f"Application location: {target_dir}")
    print("You can launch the coach anytime using the desktop shortcut or Launch Coach.bat.")
    print("When the app opens, it will prompt you for your free Google Gemini API key.")
    print("=" * 70)

    run_now = input("\nWould you like to launch VALORANT AI VOD COACH now? (Y/n): ").strip().lower()
    if run_now in ["", "y", "yes"]:
        print("Launching coach...")
        launcher_bat = target_dir / "Launch Coach.bat"
        if launcher_bat.exists():
            os.startfile(str(launcher_bat))
        else:
            subprocess.Popen([str(python_exe), "app.py"], cwd=str(target_dir))
    
    print("\nAll set! Closing installer.")

if __name__ == "__main__":
    main()

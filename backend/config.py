import os
from pathlib import Path
from dotenv import load_dotenv, set_key

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / '.env'
load_dotenv(ENV_FILE)

class Settings:
    def __init__(self):
        self.reload()

    def reload(self):
        load_dotenv(ENV_FILE, override=True)
        self.gemini_api_key = os.getenv('GEMINI_API_KEY', '').strip()
        
        # Adaptive data directory: Use configured DATA_DIR, or D:\ if available, else User Home directory
        configured_data_dir = os.getenv('DATA_DIR', '').strip()
        if configured_data_dir:
            self.data_dir = Path(configured_data_dir)
        elif Path('D:/').exists():
            self.data_dir = Path(r'D:\valorant-vod-coach-data')
        else:
            self.data_dir = Path.home() / 'valorant-vod-coach-data'

        self.host = os.getenv('HOST', '127.0.0.1')
        self.port = int(os.getenv('PORT', '8000'))
        self.gemini_model = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')

        # Add local bin folder to PATH if present (for portable ffmpeg)
        bin_dir = BASE_DIR / 'bin'
        if bin_dir.exists():
            os.environ['PATH'] = f"{str(bin_dir)};{os.environ.get('PATH', '')}"

        # Subdirectories
        self.uploads_dir = self.data_dir / 'uploads'
        self.clips_dir = self.data_dir / 'clips'
        self.reports_dir = self.data_dir / 'reports'
        self.temp_dir = self.data_dir / 'temp'
        self.db_dir = self.data_dir / 'db'
        self.db_path = self.db_dir / 'vod_coach.db'

        for d in [self.data_dir, self.uploads_dir, self.clips_dir, self.reports_dir, self.temp_dir, self.db_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def update_setting(self, key: str, value: str):
        set_key(str(ENV_FILE), key, value)
        self.reload()

settings = Settings()

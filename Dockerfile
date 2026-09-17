FROM python:3.12-slim

# Install system dependencies including FFmpeg and OpenGL
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Environment settings
ENV DATA_DIR=/data
ENV PORT=8000
ENV HOST=0.0.0.0

EXPOSE 8000

CMD ["python", "run.py"]

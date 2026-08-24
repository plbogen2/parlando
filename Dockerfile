FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (ffmpeg for audio mastering and container embedding)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install --no-cache-dir .

EXPOSE 8765

CMD ["python3", "-m", "parlando.cli", "--web", "--port", "8765", "--host", "0.0.0.0"]

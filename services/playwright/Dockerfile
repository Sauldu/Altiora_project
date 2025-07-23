FROM mcr.microsoft.com/playwright/python:v1.40.0-focal
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY playwright_runner.py .
RUN mkdir -p /app/workspace /app/reports /app/screenshots /app/videos
EXPOSE 8004
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8004/health || exit 1
CMD ["python", "playwright_runner.py", "--host", "0.0.0.0", "--port", "8004"]

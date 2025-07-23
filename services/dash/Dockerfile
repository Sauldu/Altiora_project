FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/dash /app/src/dash
CMD ["python", "-m", "src.dash.app"]

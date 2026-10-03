FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN useradd --create-home jobkit && mkdir -p /app/data && chown -R jobkit /app/data
USER jobkit

EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/auth/status')"
CMD ["python", "cli.py", "serve", "--host", "0.0.0.0", "--port", "8000"]

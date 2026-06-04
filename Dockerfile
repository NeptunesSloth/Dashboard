FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default: run the control center. Override the command to run an agent instead.
EXPOSE 8200
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8200/healthz', timeout=4).status==200 else 1)"
CMD ["uvicorn", "maybot_control_center.app:app", "--host", "0.0.0.0", "--port", "8200"]

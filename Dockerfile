FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir fastapi==0.136.3 uvicorn==0.48.0 pyyaml==6.0.3
COPY sect_academy ./sect_academy

# Progress lives in /data (mount a volume there).
ENV SECT_ACADEMY_FILE=/data/academy_state.json SECT_ACADEMY_HOST=0.0.0.0 SECT_ACADEMY_PORT=8200
VOLUME /data
EXPOSE 8200
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8200/healthz', timeout=4).status==200 else 1)"
CMD ["python", "-m", "sect_academy"]

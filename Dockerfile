FROM python:3.12-slim

WORKDIR /app

# git + the GitHub CLI (`gh`) so disciples can clone repos and open REAL pull
# requests when MAYBOT_PR_ENABLED=1. Without these, PR creation gracefully
# falls back to recording a review-only "proposed PR".
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates curl gnupg \
 && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
 && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list \
 && apt-get update && apt-get install -y --no-install-recommends gh \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default: run the control center. Override the command to run an agent instead.
EXPOSE 8200
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8200/healthz', timeout=4).status==200 else 1)"
CMD ["uvicorn", "maybot_control_center.app:app", "--host", "0.0.0.0", "--port", "8200"]

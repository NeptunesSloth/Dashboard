FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default: run the control center. Override the command to run an agent instead.
EXPOSE 8200
CMD ["uvicorn", "maybot_control_center.app:app", "--host", "0.0.0.0", "--port", "8200"]

FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
COPY scripts/ ./scripts/
ENV PYTHONPATH=/app/src
ENTRYPOINT ["python", "scripts/run_agent.py"]

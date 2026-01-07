FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pm_tools.py .

# Create data directory
RUN mkdir -p /app/output/pm

ENV PM_DATABASE_PATH=/app/output/pm/tasks.db
ENV LOG_LEVEL=INFO

EXPOSE 3334

# Initialize database on startup
ENTRYPOINT ["python", "pm_tools.py"]
CMD ["--port", "3334"]

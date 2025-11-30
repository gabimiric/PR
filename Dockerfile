FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY leader.py follower.py ./

# The CMD will be overridden in docker-compose
CMD ["uvicorn", "leader:app", "--host", "0.0.0.0", "--port", "5000"]


FROM python:3.11-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY crosafe ./crosafe
USER 10001
CMD ["uvicorn", "crosafe.api:app", "--host", "0.0.0.0", "--port", "8000"]

FROM python:3.11-slim

WORKDIR /app

# Install the feanor SDK
COPY feanor/ /app/feanor/
RUN pip install --no-cache-dir /app/feanor/

# Install extra worker dependencies
RUN pip install --no-cache-dir aiofiles boto3

# Copy worker SDK and entrypoint
COPY worker/sdk/ /app/worker/sdk/
COPY worker/__init__.py /app/worker/__init__.py
COPY worker/container_job/entrypoint.py /app/entrypoint.py

CMD ["python", "entrypoint.py"]

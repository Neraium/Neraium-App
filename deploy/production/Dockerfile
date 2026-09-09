FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY authority /opt/authority
RUN python -m venv /opt/authority-venv && /opt/authority-venv/bin/pip install --no-cache-dir -r /opt/authority/backend/requirements.txt
COPY app /opt/app
RUN python -m venv /opt/app-venv && /opt/app-venv/bin/pip install --no-cache-dir '/opt/app[dev]'
COPY runtime.py /opt/runtime/runtime.py
COPY version.json /opt/runtime/version.json
RUN useradd --uid 10001 --create-home workbench && mkdir /data && chown 10001:10001 /data && git config --system --add safe.directory /opt/authority
ENV NERAIUM_AUTHORITY_ROOT=/opt/authority NERAIUM_AUTHORITY_PYTHON=/opt/authority-venv/bin/python NERAIUM_WORKBENCH_DATA=/data
USER 10001:10001
WORKDIR /opt/runtime
EXPOSE 8000
CMD ["/opt/app-venv/bin/uvicorn", "runtime:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--timeout-keep-alive", "5"]

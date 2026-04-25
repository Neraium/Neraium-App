FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .[dev]
EXPOSE 8000
CMD ["python", "run_demo.py"]

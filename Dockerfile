FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# One worker (with threads): the request log that grades recordings and agent runs lives in the worker's memory, so a
# second worker would hold part of a session's requests that the save never sees.
CMD ["gunicorn", "run:app", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "120"]

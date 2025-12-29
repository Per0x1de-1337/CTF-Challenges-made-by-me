FROM python:3.8-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir Flask gunicorn redis

ENV FLASK_APP=app.py

EXPOSE 8080

CMD ["gunicorn", "-w", "1", "-k", "gthread", "--threads", "8", "--bind", "0.0.0.0:8080", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info", "app:app"]

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && useradd --create-home --shell /usr/sbin/nologin lesson
COPY --chown=lesson:lesson app /app/app

USER lesson
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host ${LESSON_BIND:-0.0.0.0} --port ${LESSON_PORT:-8080} --proxy-headers"]

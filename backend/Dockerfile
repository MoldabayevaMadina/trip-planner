FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN DJANGO_SECRET_KEY=build-only DB_NAME=x DB_USER=x DB_PASSWORD=x \
    python manage.py collectstatic --noinput \
 && sed -i 's/\r$//' entrypoint.sh \
 && chmod +x entrypoint.sh \
 && useradd --create-home appuser \
 && chown -R appuser /app


USER appuser

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
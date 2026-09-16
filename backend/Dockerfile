FROM python:3.14-slim

WORKDIR /srv/envychat

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends gcc default-libmysqlclient-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
FROM python:3.13-slim

WORKDIR /app

# System deps for WeasyPrint PDF rendering + lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b \
    libffi-dev libgdk-pixbuf-2.0-0 libcairo2 libxml2-dev libxslt1-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY config/ config/
COPY local_users.json .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

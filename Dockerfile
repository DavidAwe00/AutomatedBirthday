FROM python:3.11-slim

WORKDIR /app

# Install system fonts for Pillow text rendering
RUN apt-get update && apt-get install -y \
    fonts-dejavu-core \
    libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Persistent volume for SQLite DB
VOLUME ["/app/instance"]

EXPOSE 5050

ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

CMD ["python", "app.py"]

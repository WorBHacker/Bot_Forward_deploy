FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Install CPU-only torch first so pip won't pull the heavy CUDA wheel later
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Run DB migrations automatically, then start the bot
CMD ["sh", "-c", "alembic -c alembic/alembic.ini upgrade head && python -m bot.main"]

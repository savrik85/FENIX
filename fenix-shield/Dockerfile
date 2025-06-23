FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY . .

RUN adduser --disabled-password --gecos '' --uid 1000 fenix && chown -R fenix:fenix /app
USER fenix

EXPOSE 8008

CMD ["python", "-c", "import time; print('shield service placeholder - sleeping...'); time.sleep(86400)"]

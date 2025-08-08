# FENIX Server Verification Commands
**Server:** 69.55.55.8
**Path:** `/root/FENIX`

## 1. Základní Stav Služeb
```bash
# Přihlášení na server
ssh root@69.55.55.8

# Přejít do FENIX složky
cd /root/FENIX

# Zkontrolovat stav všech kontejnerů
docker compose ps

# Zkontrolovat health status
docker compose ps --format "table {{.Name}}\t{{.Status}}"
```

## 2. Aktualizace Kódu
```bash
# Stáhnout nejnovější kód z repository
git pull origin main

# Zkontrolovat že máme nejnovější commit
git log -1 --oneline

# Rebuildit kontejnery s novým kódem
docker compose build celery-worker celery-beat eagle

# Restartovat služby
docker compose restart celery-worker celery-beat eagle
```

## 3. Ověření Health Checků
```bash
# Eagle service health
curl -s http://localhost:8001/health

# Gateway service health
curl -s http://localhost:8000/health

# Redis test
docker compose exec redis redis-cli ping

# PostgreSQL test
docker compose exec postgres pg_isready -h localhost -p 5432
```

## 4. Celery Beat Scheduler Test
```bash
# Zkontrolovat že Beat běží
docker compose logs --tail=10 celery-beat

# Ověřit naplánované úlohy
docker compose exec celery-beat python -c "from src.services.scheduler import celery_app; print('Beat schedule:', celery_app.conf.beat_schedule)"

# Zkontrolovat časové nastavení
docker compose exec celery-beat python -c "from datetime import datetime; print(f'Server time: {datetime.now()}')"
```

## 5. Monitoring Konfigurace Test
```bash
# Zkontrolovat monitoring konfigurace
curl -s http://localhost:8001/monitoring/configs

# Zkontrolovat monitoring statistiky
curl -s http://localhost:8001/monitoring/stats

# Ověřit email nastavení
docker compose exec celery-worker python -c "
from src.config import settings
print(f'SMTP: {settings.smtp_server}:{settings.smtp_port}')
print(f'Email: {settings.email_username}')
print(f'Recipients: {settings.default_notification_email}')
print(f'Daily scan: {settings.daily_scan_hour}:{settings.daily_scan_minute}')
"
```

## 6. Scraping Functionality Test
```bash
# Test základního scrapingu
curl -X POST "http://localhost:8001/scrape/start" \
     -H "Content-Type: application/json" \
     -d '{"source": "sam.gov", "keywords": ["windows"], "max_results": 3}'

# Počkat 10 sekund, pak zkontrolovat výsledek
# (použij job_id z předchozího příkazu)
sleep 10
curl -s "http://localhost:8001/scrape/status/{JOB_ID}"
```

## 7. Manual Monitoring Test (volitelný)
```bash
# Spustit manuální monitoring scan
curl -X POST "http://localhost:8001/monitoring/trigger-scan" \
     -H "Content-Type: application/json" -d '{}'

# Sledovat logy
docker compose logs -f celery-worker --tail=20
```

## 8. Kritické Kontrolní Body
```bash
# 1. Zkontrolovat že .env soubor má správné hodnoty
cat .env | grep -E "(EMAIL_|SMTP_|DAILY_SCAN_)"

# 2. Ověřit že kontejnery mají nejnovější kód
docker compose exec celery-worker head -15 /app/src/services/scheduler.py

# 3. Zkontrolovat že cleanup metoda existuje
docker compose exec celery-worker tail -10 /app/src/services/http_client_service.py

# 4. Ověřit databázové připojení
docker compose exec postgres psql -U fenix -d fenix -c "SELECT count(*) FROM monitoring_configs WHERE is_active = true;"
```

## 9. Finální Ověření
```bash
# Zkontroluj že všechny služby jsou healthy
docker compose ps | grep -c "healthy"

# Mělo by vrátit minimálně 4 (eagle, gateway, celery-worker, celery-beat)

echo "🎯 FENIX Server Verification Complete!"
echo "✅ Pokud všechny testy prošly, systém je připraven pro zítřejší 8:00 běh"
```

## ⚠️ Co Kontrolovat
- Všechny kontejnery mají status "healthy"
- Curl requesty vracejí HTTP 200 a validní JSON
- Celery Beat má nakonfigurované správné úlohy
- Email konfigurace je správně nastavená
- Scraping test se dokončí za 2-10 sekund s reálnými daty

## 🚨 Pokud Něco Nefunguje
```bash
# Zkontroluj logy pro chyby
docker compose logs celery-worker --tail=50
docker compose logs eagle --tail=50
docker compose logs postgres --tail=20

# Restartuj všechny služby
docker compose down
docker compose up -d

# Čekej na healthy status
sleep 30
docker compose ps
```

# FENIX Dashboard

Jednoduchá webová stránka pro přehled získaných dat z FENIX systému.

## Funkce

- **Přehled tendrů/zakázek**: Tabulka s daty získanými ze scrapingu
- **Statistiky**: Počet zpracovaných zakázek, úspěšnost, zdroje
- **Filtry**: Podle zdroje, data, relevance skóre
- **Detail zakázky**: Zobrazení detailních informací po kliknutí
- **Auto-refresh**: Automatické obnovení dat každých 30 sekund

## Spuštění

### S Docker Compose
```bash
# Spuštění celého FENIX systému včetně dashboard
docker compose up -d

# Dashboard bude dostupný na: http://localhost:8080
```

### Lokální vývoj (bez Dockeru)
```bash
# Spuštění jednoduchého HTTP serveru
cd fenix-dashboard
python3 -m http.server 8080

# Nebo s Node.js
npx http-server . -p 8080 -c-1

# Dashboard bude dostupný na: http://localhost:8080
```

## API Požadavky

Dashboard komunikuje s následujícími API endpointy:

- `GET /scrape/jobs` - Seznam všech scraping úloh
- `GET /scrape/results/{job_id}` - Výsledky konkrétní úlohy
- `GET /monitoring/stats` - Statistiky systému

## Technologie

- **Frontend**: HTML5, CSS3 (Tailwind CSS), Vanilla JavaScript
- **API**: Fetch API pro komunikaci s backend službami
- **Webový server**: Nginx (v Docker kontejneru)
- **Responsivní design**: Funguje na mobilech i desktopu

## Konfigurace

### CORS
API endpointy musí mít povolený CORS pro doménu dashboard serveru.

### Environment
Dashboard podporuje následující proměnné prostředí:
- `ENVIRONMENT`: production/development (výchozí: production)

## Struktura souborů

```
fenix-dashboard/
├── Dockerfile          # Docker konfigurace
├── nginx.conf          # Nginx konfigurace
├── index.html          # Hlavní HTML stránka
└── README.md           # Tato dokumentace
```

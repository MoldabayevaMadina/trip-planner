# Trip Planner

Plan a trip day by day: places on a map with the route of the day, and the weather for every day of the trip.

**Stack:** Django 5 + Django REST Framework, PostgreSQL 16, Gunicorn, WhiteNoise, Docker Compose, Leaflet + OpenStreetMap.
**External services (free, no API keys):** Nominatim (geocoding), Open-Meteo (weather).

## Run with Docker

Copy `.env.example` to `.env` (on Windows: `copy .env.example .env`) and replace every `change_me` with your own values. Then run:

```bash
cp .env.example .env
docker compose up --build
```

- App: http://localhost:8000
- API: http://localhost:8000/api/trips/
- Admin: http://localhost:8000/admin/ (credentials from `DJANGO_SUPERUSER_*` in `.env`)

## Features

- Create a trip by city and dates: the city is geocoded, a day is created for every date.
- Add places by name (coordinates are found automatically) or with exact coordinates.
- Map with numbered pins and the route of the selected day.
- Weather for every day: forecast up to ~2 weeks ahead, same dates last year for later trips, cached in the database for 3 hours.
- Mark places as visited, set the visit time, move places between days.

## Docker setup

| Requirement | Implementation |
|---|---|
| Services | `db` (postgres:16-alpine) and `backend` (custom `backend/Dockerfile`) in `compose.yaml` |
| Network | bridge network `trip-net`; the backend connects to the database by service name `db` |
| Ports | only the backend is published (`HOST_PORT:8000`); the database is not exposed |
| Dependencies | `depends_on` with `condition: service_healthy` + `pg_isready` healthcheck |
| Configuration and secrets | environment variables from `.env` (git-ignored); `.env.example` is the template |
| Persistence | named volume `pgdata` mounted to `/var/lib/postgresql/data` |
| Startup | `entrypoint.sh`: migrations → admin user → Gunicorn, running as a non-root user |

Data survives recreating the containers: `docker compose down` removes the containers but keeps the volume, so after `docker compose up -d` all trips and places are still there.

```bash
docker compose down
docker compose up -d
```

## API

| Method | Endpoint | Description |
|---|---|---|
| GET, POST | `/api/trips/` | List trips / create a trip (`city`, `start_date`, `end_date`, optional `title`) |
| GET, PATCH, PUT, DELETE | `/api/trips/{id}/` | One trip |
| GET | `/api/trips/{id}/days/` | Days with places and weather |
| GET, PATCH | `/api/days/{id}/` | One day (e.g. a note) |
| GET, POST | `/api/days/{id}/places/` | Places of a day / add a place (`name`, optional `latitude`, `longitude`, `time`, `category`) |
| GET, PATCH, DELETE | `/api/places/{id}/` | One place: mark visited, change time, move to another day |
# Trip Planner

Plan a trip day by day: places on a map with the route of the day, and the weather for every day of the trip.

**Stack:** Django 5 + Django REST Framework, PostgreSQL 16, Gunicorn, WhiteNoise, Docker Compose, Leaflet + OpenStreetMap.
**External services (free, no API keys):** Nominatim (geocoding), Open-Meteo (weather).
**API docs:** drf-spectacular (OpenAPI 3, Swagger UI). **API testing:** Postman collection.

## Run with Docker

Copy `.env.example` to `.env` (on Windows: `copy .env.example .env`) and replace every `change_me` with your own values. Then run:

```bash
cp .env.example .env
docker compose up --build
```

- App: http://localhost:8000
- API: http://localhost:8000/api/trips/
- API docs (Swagger UI): http://localhost:8000/api/docs/
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

## API documentation

- **Swagger UI:** http://localhost:8000/api/docs/ — interactive docs, every endpoint can be tried with "Try it out"
- **ReDoc:** http://localhost:8000/api/redoc/
- **OpenAPI schema:** [`docs/openapi.yaml`](docs/openapi.yaml) (also served at `/api/schema/`)

The docs are generated from the code with **drf-spectacular**, so they always match the API.

### Endpoints

| Method | Endpoint | Description | Responses |
|---|---|---|---|
| GET | `/api/trips/` | List trips | 200 |
| POST | `/api/trips/` | Create a trip (`city`, `start_date`, `end_date`, optional `title`); the city is geocoded and a day is created for every date | 201, 400, 503 |
| GET | `/api/trips/{id}/` | One trip | 200, 404 |
| PUT / PATCH | `/api/trips/{id}/` | Full / partial update; days are re-synced if the dates change | 200, 400, 404 |
| DELETE | `/api/trips/{id}/` | Delete a trip with its days and places | 204, 404 |
| GET | `/api/trips/{id}/days/` | Days with places and weather | 200, 404 |
| GET | `/api/days/{id}/` | One day | 200, 404 |
| PUT / PATCH | `/api/days/{id}/` | Change the day's note (the date is read-only) | 200, 400, 404 |
| GET | `/api/days/{id}/places/` | Places of a day | 200, 404 |
| POST | `/api/days/{id}/places/` | Add a place (`name`, optional `latitude` + `longitude`, `time`, `category`); coordinates are found by name if not sent | 201, 400, 404, 503 |
| GET | `/api/places/{id}/` | One place | 200, 404 |
| PUT / PATCH | `/api/places/{id}/` | Update a place: mark visited, change time, move to another day of the same trip | 200, 400, 404 |
| DELETE | `/api/places/{id}/` | Delete a place | 204, 404 |

**Errors:**
- `400` — invalid data: end date before start date, missing required fields, city not found, only one coordinate sent, moving a place to another trip's day;
- `404` — object not found;
- `405` — method not allowed (e.g. `DELETE /api/days/{id}/`: days are deleted together with their trip);
- `503` — external service (Nominatim / Open-Meteo) is unavailable.

## Postman

Collection: [`postman/TripPlanner.postman_collection.json`](postman/TripPlanner.postman_collection.json) — 26 requests covering all endpoints and error cases.

1. Start the app: `docker compose up -d --build`
2. In Postman: **Import** → select the collection file.
3. Right-click the collection → **Run collection** → set a delay of **1000 ms** (Nominatim allows 1 request per second) → **Run**.

Requests are ordered as a scenario: create a trip → get its days → add places → mark visited → move → delete → error cases → cleanup.
IDs of created objects are saved to collection variables automatically (`tripId`, `dayId`, `placeId`…), and every request has tests for the expected status code.

## Project structure

```
├── compose.yaml
├── .env.example
├── docs/openapi.yaml                  # API documentation (OpenAPI 3)
├── postman/TripPlanner.postman_collection.json
└── backend/
    ├── Dockerfile
    ├── entrypoint.sh
    ├── requirements.txt
    ├── config/                         # settings, root URLs
    └── trips/
        ├── models.py                   # Trip, Day, Place, User
        ├── serializers.py              # validation + JSON format
        ├── views.py                    # API endpoints
        ├── services.py                 # Nominatim and Open-Meteo integrations
        ├── urls.py
        └── templates/, static/         # web page with the map
```
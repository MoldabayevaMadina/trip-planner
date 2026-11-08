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
- All places of a trip in one list; filter places by trip, visited status and category.
- Preview a place search before adding it; health check of the backend and the database.

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

### Data model

```
User            (custom user model, used for authentication in the next step)
Trip   1 ──── * Day      Day.trip   → ForeignKey(Trip,  on_delete=CASCADE, related_name="days")
Day    1 ──── * Place    Place.day  → ForeignKey(Day,   on_delete=CASCADE, related_name="places")
```

- **Trip**: `title`, `city`, `country`, `latitude`, `longitude`, `start_date`, `end_date`, `created_at`
- **Day**: `trip`, `date` (unique per trip), `note`, cached weather (`weather_code`, `temp_max`, `temp_min`, `weather_source`, `weather_updated_at`)
- **Place**: `day`, `name`, `address`, `latitude`, `longitude`, `time`, `category`, `visited`, `created_at`

### Endpoints

10 URLs, 20 operations (method + URL).

| Method | Endpoint | Description | Responses |
|---|---|---|---|
| GET | `/api/trips/` | List trips | 200 |
| POST | `/api/trips/` | Create a trip (`city`, `start_date`, `end_date`, optional `title`); the city is geocoded and a day is created for every date | 201, 400, 503 |
| GET | `/api/trips/{id}/` | One trip | 200, 404 |
| PUT / PATCH | `/api/trips/{id}/` | Full / partial update; days are re-synced if the dates change | 200, 400, 404 |
| DELETE | `/api/trips/{id}/` | Delete a trip with its days and places | 204, 404 |
| GET | `/api/trips/{id}/days/` | Days with places and weather | 200, 404 |
| GET | `/api/trips/{id}/places/` | All places of a trip, ordered by day and time | 200, 404 |
| GET | `/api/days/{id}/` | One day | 200, 404 |
| PUT / PATCH | `/api/days/{id}/` | Change the day's note (the date is read-only) | 200, 400, 404 |
| GET | `/api/days/{id}/places/` | Places of a day | 200, 404 |
| POST | `/api/days/{id}/places/` | Add a place (`name`, optional `latitude` + `longitude`, `time`, `category`); coordinates are found by name if not sent | 201, 400, 404, 503 |
| GET | `/api/places/{id}/` | One place | 200, 404 |
| PUT / PATCH | `/api/places/{id}/` | Update a place: mark visited, change time, move to another day of the same trip | 200, 400, 404 |
| DELETE | `/api/places/{id}/` | Delete a place | 204, 404 |
| GET | `/api/places/` | All places; filters: `?trip=`, `?visited=`, `?category=` (can be combined) | 200, 400 |
| GET | `/api/geocode/?q=` | Preview a place search (nothing is saved) | 200, 400, 503 |
| GET | `/api/health/` | Backend and database status | 200, 503 |

### Query parameters

| Endpoint | Parameter | Values | Example |
|---|---|---|---|
| `/api/places/` | `trip` | trip id | `/api/places/?trip=3` |
| `/api/places/` | `visited` | `true` / `false` | `/api/places/?trip=3&visited=true` |
| `/api/places/` | `category` | `sight`, `museum`, `food`, … (see `Place.Category`) | `/api/places/?category=food` |
| `/api/geocode/` | `q` (required) | text, at least 2 characters | `/api/geocode/?q=Galata Tower, Istanbul` |

### Request and response examples

Create a trip:

```http
POST /api/trips/
Content-Type: application/json

{"city": "Istanbul", "start_date": "2026-11-10", "end_date": "2026-11-13", "title": "Istanbul with friends"}
```

`201 Created`

```json
{"id": 7, "title": "Istanbul with friends", "city": "Istanbul", "country": "Türkiye",
 "latitude": 41.0082, "longitude": 28.9784, "start_date": "2026-11-10", "end_date": "2026-11-13",
 "places_count": 0, "created_at": "2026-11-08T10:00:00Z"}
```

Add a place by name (coordinates and address are found by the server):

```http
POST /api/days/41/places/
Content-Type: application/json

{"name": "Galata Tower", "time": "16:00", "category": "sight"}
```

`201 Created`

```json
{"id": 15, "day": 41, "name": "Galata Tower", "address": "Galata Kulesi, Beyoğlu, İstanbul, Türkiye",
 "latitude": 41.0256, "longitude": 28.9741, "time": "16:00:00", "category": "sight", "visited": false}
```

Validation error:

```http
POST /api/trips/
{"city": "Istanbul", "start_date": "2026-11-13", "end_date": "2026-11-10"}
```

`400 Bad Request`

```json
{"end_date": ["End date can't be before start date."]}
```

The full schema of every request and response is in Swagger UI and `docs/openapi.yaml`.

**Errors:**
- `400` — invalid data: end date before start date, missing required fields, city not found, only one coordinate sent, moving a place to another trip's day, invalid filter value (`?category=pizza`), too short search query;
- `404` — object not found;
- `405` — method not allowed (e.g. `DELETE /api/days/{id}/`: days are deleted together with their trip);
- `503` — external service (Nominatim / Open-Meteo) or the database is unavailable.

## Postman

Collection: [`postman/TripPlanner.postman_collection.json`](postman/TripPlanner.postman_collection.json) — 34 requests covering all endpoints and error cases.

| Folder | What it checks |
|---|---|
| 1. Trips | list, create, get, PUT, PATCH, days with weather |
| 2. Days | get, note (PATCH / PUT), places of a day |
| 3. Places | add by name / with coordinates, get, mark visited, move to another day, all places of a trip, filters, PUT, delete |
| 4. Validation & errors | 400 (invalid dates, missing fields, city not found, one coordinate, short query, unknown category), 404, 405 |
| 5. Cleanup | delete the trip, check it is gone (404) |
| 6. Service | health check, geocode preview |

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
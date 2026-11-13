# Trip Planner

Plan a trip day by day: places on a map with the route of the day, the weather for every day of the trip, and the countries you travel to (with visa-free information).

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

### Demo data

```bash
docker compose exec backend python manage.py seed_demo
```

Adds 6 trips to 5 countries (a past trip, a current one and upcoming ones), 21 places and 24 visits; two trips to Istanbul share places, Turkey, Georgia and the UAE are marked visa-free. Dates are counted from the day you run the command, no external services are called, and running it again does not duplicate anything. The visa information is demo data: check official sources before a real trip.

## Features

- Create a trip by city and dates: the city is geocoded, its country is linked, a day is created for every date.
- Plan places for each day: by name (found on the map near the trip's city), by clicking on the map, or by reusing a place you already have.
- Places are a shared catalog: the same real place is stored once and can be planned in many days of many trips.
- Map with numbered pins and the route of the selected day.
- Weather for every day: forecast up to ~2 weeks ahead, same dates last year for later trips, cached in the database for 3 hours.
- Countries with visa-free information; filter trips by country, city, date, period or visa-free countries.
- Navigate relations in both directions: trip → days → places, and place → days → trips, country → trips / places, date → trips.
- Trip statistics, copying a trip to new dates, the list of cities and the most popular places.

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

Data survives recreating the containers: `docker compose down` removes the containers but keeps the volume. `docker compose down -v` also deletes the database.

## Data model

```
Country 1 ──── * Trip       Trip.country → ForeignKey(Country, PROTECT, related_name="trips")
Trip    1 ──── * Day        Day.trip     → ForeignKey(Trip, CASCADE, related_name="days")
Day     * ──── * Place      Place.days   → ManyToManyField(Day, through="Visit", related_name="places")
                            Visit.day    → ForeignKey(Day, CASCADE, related_name="visits")
                            Visit.place  → ForeignKey(Place, PROTECT, related_name="visits")
User                        custom user model (authentication arrives in HW4)
```

| Model | Fields | Notes |
|---|---|---|
| **Country** | `code` (ISO, unique), `name`, `visa_free`, `visa_free_days` | created automatically from the geocoder; visa info is edited via the API |
| **Trip** | `title`, `city`, `country`, `latitude`, `longitude`, `start_date`, `end_date`, `created_at` | coordinates and country are found by the server |
| **Day** | `trip`, `date`, `note`, cached weather (`weather_code`, `temp_max`, `temp_min`, `weather_source`, `weather_updated_at`) | unique `(trip, date)` |
| **Place** | `name`, `address`, `latitude`, `longitude`, `category`, `osm_id` (unique), `created_at` | a real place, shared by all trips |
| **Visit** | `day`, `place`, `time`, `visited`, `created_at` | a place planned for a day; unique `(day, place)` |

Relationships: four one-to-many (`Country → Trip`, `Trip → Day`, `Day → Visit`, `Place → Visit`) and one many-to-many (`Day ↔ Place` through `Visit`).

## API documentation

- **Swagger UI:** http://localhost:8000/api/docs/ — interactive docs, every endpoint can be tried with "Try it out"
- **OpenAPI schema:** [`docs/openapi.yaml`](docs/openapi.yaml) (also served at `/api/schema/`)

The docs are generated from the code with **drf-spectacular**, so they always match the API.

### Endpoints

24 URLs, 38 operations (method + URL).

**Trips**

| Method | Endpoint | Description | Responses |
|---|---|---|---|
| GET | `/api/trips/` | List trips sorted by start date; filters below | 200, 400 |
| POST | `/api/trips/` | Create a trip (`city`, `start_date`, `end_date`, optional `title`); the city is geocoded, the country is linked, a day is created for every date | 201, 400, 503 |
| GET | `/api/trips/{id}/` | One trip with its country | 200, 404 |
| PUT / PATCH | `/api/trips/{id}/` | Full / partial update; a new city is geocoded, days are re-synced if the dates change | 200, 400, 404, 503 |
| DELETE | `/api/trips/{id}/` | Delete a trip with its days and visits (places stay in the catalog) | 204, 404 |
| GET | `/api/trips/{id}/days/` | Days with visits and weather | 200, 404 |
| GET | `/api/trips/{id}/places/` | Places planned in the trip (each once) | 200, 404 |
| GET | `/api/trips/{id}/stats/` | Statistics: days, planned visits, unique places, visited (%), rainy days, visits by category and by day | 200, 404 |
| POST | `/api/trips/{id}/copy/` | Copy the trip with its plan to new dates: `{"start_date": "2027-03-01", "title": "..."}`; visits are copied as not visited | 201, 400, 404 |
| GET | `/api/dates/{YYYY-MM-DD}/trips/` | Trips that go on this date | 200, 400 |
| GET | `/api/cities/` | Cities with the number of trips; filter `country` | 200 |

**Days**

| Method | Endpoint | Description | Responses |
|---|---|---|---|
| GET | `/api/days/{id}/` | One day with its trip id, weather and visits | 200, 404 |
| PUT / PATCH | `/api/days/{id}/` | Change the day's note (date and trip are read-only) | 200, 400, 404 |
| GET | `/api/days/{id}/visits/` | The plan of the day | 200, 404 |
| POST | `/api/days/{id}/visits/` | Add a place to the day: existing `{"place": 7}`, new by name `{"name": "Galata Tower"}`, or new with `latitude` + `longitude`; optional `time`, `category`, `visited` | 201, 400, 404, 503 |
| GET | `/api/days/{id}/places/` | Places of the day (many-to-many) | 200, 404 |

**Visits**

| Method | Endpoint | Description | Responses |
|---|---|---|---|
| GET | `/api/visits/` | All visits; filters `trip`, `date`, `visited`, `category` | 200, 400 |
| GET | `/api/visits/{id}/` | One visit | 200, 404 |
| PUT / PATCH | `/api/visits/{id}/` | Mark visited, change time, move to another day of the same trip (`{"day": 12}`) | 200, 400, 404 |
| DELETE | `/api/visits/{id}/` | Remove the place from the day (the place stays in the catalog) | 204, 404 |

**Places (catalog)**

| Method | Endpoint | Description | Responses |
|---|---|---|---|
| GET | `/api/places/` | All places; filters `category`, `search`, `trip` | 200, 400 |
| GET | `/api/places/{id}/` | One place | 200, 404 |
| PUT / PATCH | `/api/places/{id}/` | Rename, change category or coordinates | 200, 400, 404 |
| DELETE | `/api/places/{id}/` | Delete a place that is not planned anywhere | 204, 404, 409 |
| GET | `/api/places/{id}/trips/` | Trips that visit this place | 200, 404 |
| GET | `/api/places/{id}/days/` | Days (of any trip) when this place is planned | 200, 404 |
| GET | `/api/places/popular/` | Places planned in the most trips; `?limit=` 1–50 (default 10) | 200, 400 |

**Countries**

| Method | Endpoint | Description | Responses |
|---|---|---|---|
| GET | `/api/countries/` | Countries with the number of trips; filter `visa_free` | 200, 400 |
| GET | `/api/countries/{id}/` | One country | 200, 404 |
| PATCH | `/api/countries/{id}/` | Set visa info: `{"visa_free": true, "visa_free_days": 30}` | 200, 400, 404 |
| GET | `/api/countries/{id}/trips/` | All trips to this country | 200, 404 |
| GET | `/api/countries/{id}/places/` | Places planned in trips to this country | 200, 404 |

**Service**

| Method | Endpoint | Description | Responses |
|---|---|---|---|
| GET | `/api/geocode/?q=` | Preview a place search (nothing is saved) | 200, 400, 503 |
| GET | `/api/health/` | Backend and database status | 200, 503 |

### Query parameters (filters can be combined)

| Endpoint | Parameter | Values | Example |
|---|---|---|---|
| `/api/trips/` | `city` | part of the city name | `?city=ist` |
| `/api/trips/` | `country` | ISO code | `?country=TR` |
| `/api/trips/` | `visa_free` | `true` / `false` | `?visa_free=true` |
| `/api/trips/` | `date` | `YYYY-MM-DD` — trips going on this date | `?date=2026-11-21` |
| `/api/trips/` | `date_from`, `date_to` | `YYYY-MM-DD` — trips that overlap the period (one border is enough) | `?date_from=2026-11-01&date_to=2026-11-30` |
| `/api/trips/` | `search` | text in title or city | `?search=friends` |
| `/api/trips/` | `status` | `upcoming` / `current` / `past` (compared with today) | `?status=upcoming` |
| `/api/trips/` | `ordering` | `start_date`, `title`, `city`, `created_at`; `-` = descending | `?ordering=-start_date` |
| `/api/visits/` | `trip`, `date`, `visited`, `category` | id, date, `true`/`false`, category | `?trip=3&visited=false` |
| `/api/places/` | `category`, `search`, `trip` | category, text, trip id | `?category=food&trip=3` |
| `/api/countries/` | `visa_free` | `true` / `false` | `?visa_free=true` |
| `/api/cities/` | `country` | ISO code | `?country=TR` |
| `/api/places/popular/` | `limit` | 1–50 | `?limit=5` |
| `/api/geocode/` | `q` (required) | text, at least 2 characters | `?q=Galata Tower, Istanbul` |

Categories: `sight`, `museum`, `food`, `walk`, `shopping`, `other`.

### Request and response examples

Create a trip:

```http
POST /api/trips/
Content-Type: application/json

{"city": "Istanbul", "start_date": "2026-11-20", "end_date": "2026-11-23", "title": "Istanbul with friends"}
```

`201 Created`

```json
{"id": 1, "title": "Istanbul with friends", "city": "Istanbul",
 "country": {"id": 1, "code": "TR", "name": "Turkey", "visa_free": false},
 "latitude": 41.006381, "longitude": 28.9758715, "start_date": "2026-11-20", "end_date": "2026-11-23",
 "places_count": 0, "created_at": "2026-11-11T18:58:58+05:00"}
```

Add a place to a day by name (coordinates and address are found by the server):

```http
POST /api/days/1/visits/
Content-Type: application/json

{"name": "Galata Tower", "time": "16:00", "category": "sight"}
```

`201 Created`

```json
{"id": 1, "day": 1, "place": 1, "name": "Galata Tower", "address": "Galata Kulesi, Beyoğlu, İstanbul, Türkiye",
 "latitude": 41.0256, "longitude": 28.9741, "category": "sight", "time": "16:00:00", "visited": false,
 "created_at": "2026-11-11T19:05:00+05:00"}
```

Reuse the same place in another trip, then see all trips of the place:

```http
POST /api/days/7/visits/
{"place": 1}

GET /api/places/1/trips/
```

Mark a country visa-free and list trips to visa-free countries:

```http
PATCH /api/countries/1/
{"visa_free": true, "visa_free_days": 30}

GET /api/trips/?visa_free=true
```

Statistics of a trip (counted by the database with `aggregate` / `annotate`):

```http
GET /api/trips/1/stats/
```

```json
{"trip": 1, "title": "Istanbul in autumn", "days": 4, "planned_visits": 5, "unique_places": 5,
 "visited": 4, "visited_percent": 80, "rainy_days": 0,
 "by_category": {"food": 1, "museum": 2, "shopping": 1, "sight": 1},
 "by_day": [{"date": "2026-10-04", "planned": 3, "visited": 3}, {"date": "2026-10-05", "planned": 2, "visited": 1}, ...]}
```

Copy a trip to new dates:

```http
POST /api/trips/1/copy/
{"start_date": "2027-05-01"}
```

→ `201 Created`: "Istanbul in autumn (copy)", 1–4 May 2027, the same places on the same days, not visited.

Validation errors:

```json
POST /api/trips/  {"city": "Istanbul", "start_date": "2026-11-13", "end_date": "2026-11-10"}
→ 400 {"end_date": ["End date can't be before start date."]}

POST /api/days/1/visits/  {"place": 1}     (already planned for this day)
→ 400 {"place": ["This place is already planned for this day."]}

DELETE /api/places/1/                      (still planned in some day)
→ 409 {"detail": "The place is planned in 2 visit(s). Remove the visits first."}
```

**Errors:**
- `400` — invalid data: end date before start date, a trip longer than 30 days, missing fields, city or place not found, only one coordinate, a place already planned for the day, moving a visit to another trip's day, visa-free days for a visa country, invalid filter values (`status`, `ordering`, `limit`…), `date_from` after `date_to`, copying without `start_date`;
- `404` — object not found;
- `405` — method not allowed (`DELETE /api/days/{id}/`: days follow the trip dates; `PUT`/`DELETE` on countries);
- `409` — a place that is planned in some day can't be deleted;
- `503` — external service (Nominatim / Open-Meteo) or the database is unavailable.

## Postman

Collection: [`postman/TripPlanner.postman_collection.json`](postman/TripPlanner.postman_collection.json) — 87 requests covering all endpoints and error cases.

| Folder | What it checks |
|---|---|
| 1. Trips | list, create two trips in the same country, get, PUT, PATCH, days with weather |
| 2. Days | get (with trip id), note (PATCH / PUT) |
| 3. Visits | add by name / existing place / coordinates, the same place in another trip, plan of a day, places of a day, mark visited, move, PUT, filters, delete |
| 4. Places | catalog, search, places of a trip, trips of a place, days of a place, PATCH, delete, popular places |
| 5. Countries | list, get, mark visa-free, visa-free filter, trips of a country, places of a country |
| 6. Trip filters | visa-free countries, country + city, date, period, trips on a date, search, status (upcoming / current / past), ordering |
| 7. Stats, copy, cities | trip statistics, copy a trip, visits of the copy, cities, cities of a country |
| 8. Validation & errors | 400, 404, 405, 409 cases |
| 9. Service | health check, geocode preview |
| 10. Cleanup | delete the trips and the copy, the place stays in the catalog, then delete it if unused |

1. Start the app: `docker compose up -d --build`
2. In Postman: **Import** → select the collection file.
3. Right-click the collection → **Run collection** → set a delay of **1000 ms** (Nominatim allows 1 request per second) → **Run**.

IDs of created objects are saved to collection variables automatically (`tripId`, `dayId`, `placeId`, `visitId`, `countryId`, `copyId`…), and every request has tests. The collection creates and deletes its own trips, so it works on an empty database and next to demo data.

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
        ├── models.py                   # Country, Trip, Day, Place, Visit, User
        ├── serializers.py              # validation + JSON format
        ├── filters.py                  # query parameter helpers
        ├── views.py                    # API endpoints
        ├── services.py                 # Nominatim and Open-Meteo integrations
        ├── urls.py
        ├── admin.py
        ├── management/commands/seed_demo.py   # demo data
        └── templates/, static/         # web page with the map
```
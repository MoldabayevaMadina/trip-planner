# Trip Planner

A full-stack app for planning a trip day by day: places on a map with the route of the day, the weather for every day, and the countries you travel to (with visa-free information). Users sign up, log in with JWT, and see only their own trips.

**Backend:** Django 5 + Django REST Framework, Simple JWT, PostgreSQL 16, Gunicorn, WhiteNoise.
**Frontend:** React (Vite), React Router, React Leaflet + OpenStreetMap, served by nginx.
**Infrastructure:** Docker Compose with three services: `db`, `backend`, `frontend`.
**External services (free, no API keys):** Nominatim (geocoding), Photon (place autocomplete), Open-Meteo (weather).
**API docs:** drf-spectacular (OpenAPI 3, Swagger UI). **API testing:** Postman collection.

## Run with Docker

Copy `.env.example` to `.env` (on Windows: `copy .env.example .env`) and replace every `change_me` with your own values. Then run:

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec backend python manage.py seed_demo
```

| What | URL |
|---|---|
| Web app (React) | http://localhost:8080 |
| API | http://localhost:8080/api/ (also directly at http://localhost:8000/api/) |
| API docs (Swagger UI) | http://localhost:8080/api/docs/ |
| Admin | http://localhost:8080/admin/ (credentials from `DJANGO_SUPERUSER_*` in `.env`) |

**Demo login:** `demo` / `TripPlanner2026!`. This is a demo-only password created by `seed_demo`. It can be changed with the `DEMO_PASSWORD` variable in `.env` before seeding.

### Demo data

`seed_demo` fills every table with at least 10 records:

| Table | Records |
|---|---|
| Users + Profiles | 10 users (`demo`, `aigerim`, `daniyar`, `madina`, `timur`, `zhanna`, `arman`, `dana`, `nurlan`, `alina`), each with a profile |
| Countries | 12 (some marked visa-free) |
| Places | 40 |
| Trips | 15 (`demo` has 6, every other user has 1) |
| Days, Visits | a day for every date of every trip, places planned on the days |

Dates are counted from the day you run the command, no external services are called, and running it again does not duplicate anything. The visa information is demo data: check official sources before a real trip.

## Features

**Authentication**
- Sign up, log in, log out; JWT access + refresh tokens.
- The access token is refreshed automatically when it expires; if the refresh token is no longer valid, the user is logged out.
- Profile page: current user info, change username / email / home city / bio, change password.

**Trips (logged-in users only, each user sees only their own trips)**
- Create a trip by city and dates: the city is geocoded, its country is linked, a day is created for every date.
- Plan places for each day: search with autocomplete, click on the map, or reuse a place you already have.
- Map with numbered pins and the route of the selected day.
- Weather for every day: forecast up to ~2 weeks ahead, same dates last year for later trips, cached for 3 hours.
- Edit and delete trips, mark visits as visited, change time, move a visit to another day.

**Public pages (no login)**
- Home page with popular places and visa-free countries.
- Read-only API for countries, places and popular places.

## Frontend

| Route | Access | Page |
|---|---|---|
| `/` | public | Home: features, popular places, visa-free countries |
| `/login`, `/login?mode=signup` | public | Log in / Sign up |
| `/trips` | **protected** | My trips |
| `/trips/new`, `/trips/:id/edit` | **protected** | Create / edit a trip |
| `/trips/:id` | **protected** | Trip plan: days, map, places, weather |
| `/profile` | **protected** | Profile: user info, edit profile, change password |

- `ProtectedRoute` redirects a guest to `/login` and returns them to the page they wanted after login.
- `AuthProvider` keeps the current user; tokens are stored in `localStorage`.
- `api.js` adds `Authorization: Bearer <access>` to every request, refreshes the token once on `401` and repeats the request.
- Every page shows a loading state and API errors (field errors under the form fields, general errors in a message).

## Authentication API

| Method | Endpoint | Access | Description | Responses |
|---|---|---|---|---|
| POST | `/api/auth/register/` | public | `{"username", "password", "email"?}` → user + tokens | 201, 400 |
| POST | `/api/auth/login/` | public | `{"username", "password"}` → `{"access", "refresh"}` | 200, 401 |
| POST | `/api/auth/refresh/` | public | `{"refresh"}` → new `{"access"}` | 200, 401 |
| GET | `/api/auth/me/` | login | Current user with profile and number of trips | 200, 401 |
| PATCH | `/api/auth/me/` | login | Update `username`, `email`, `profile.home_city`, `profile.bio` | 200, 400, 401 |
| POST | `/api/auth/change-password/` | login | `{"old_password", "new_password"}` | 200, 400, 401 |

Protected requests send the header:

```http
Authorization: Bearer <access token>
```

- Passwords are checked by Django password validators (length, common passwords, similarity to the username, only digits) and stored as hashes.
- Access token lives 30 minutes, refresh token 7 days (`JWT_ACCESS_MINUTES`, `JWT_REFRESH_DAYS` in `.env`).

### Who can do what

| Data | Guest | Logged-in user |
|---|---|---|
| Countries, places, popular places, health | read (GET) | read + edit |
| Trips, days, visits, stats, copy, cities | `401` | only **own** objects; someone else's trip → `404` |
| Place suggestions, geocode preview | `401` | yes |

- Default permission: `IsAuthenticatedOrReadOnly`, so every `POST`/`PUT`/`PATCH`/`DELETE` needs a token.
- Trip views use `IsAuthenticated` and filter the queryset by `owner=request.user`. Someone else's trip returns `404`, not `403`, so the API does not even reveal that it exists.
- The owner of a new trip is set by the server from the token, it can't be sent in the request.

## Docker setup

| Requirement | Implementation |
|---|---|
| Services | `db` (postgres:16-alpine), `backend` (`backend/Dockerfile`), `frontend` (`frontend/Dockerfile`) in `compose.yaml` |
| Frontend image | multi-stage build: `node:22-alpine` builds the React app, `nginx:1.27-alpine` serves it |
| nginx | serves the built app; `/api/`, `/admin/`, `/static/` are proxied to `backend:8000`; other paths return `index.html` (React Router) |
| Network | bridge network `trip-net`; services reach each other by name (`db`, `backend`) |
| Ports | frontend `FRONTEND_PORT:80` (8080), backend `HOST_PORT:8000`; the database is not exposed |
| Dependencies | `backend` waits for `db` (`condition: service_healthy` + `pg_isready`), `frontend` depends on `backend` |
| Configuration and secrets | environment variables from `.env` (git-ignored); `.env.example` is the template; external service URLs are also configurable |
| Persistence | named volume `pgdata` mounted to `/var/lib/postgresql/data` |
| Startup | `entrypoint.sh`: migrations → admin user → Gunicorn, running as a non-root user |

`docker compose down` removes the containers but keeps the data. `docker compose down -v` also deletes the database.

## Data model

```
User    1 ──── 1 Profile    Profile.user → OneToOneField(User, CASCADE, related_name="profile")
User    1 ──── * Trip       Trip.owner   → ForeignKey(User, CASCADE, related_name="trips")
Country 1 ──── * Trip       Trip.country → ForeignKey(Country, PROTECT, related_name="trips")
Trip    1 ──── * Day        Day.trip     → ForeignKey(Trip, CASCADE, related_name="days")
Day     * ──── * Place      Place.days   → ManyToManyField(Day, through="Visit", related_name="places")
                            Visit.day    → ForeignKey(Day, CASCADE, related_name="visits")
                            Visit.place  → ForeignKey(Place, PROTECT, related_name="visits")
```

| Relationship | Type | Meaning |
|---|---|---|
| User ↔ Profile | **one-to-one** | every user has one profile with extra info (home city, bio) |
| User → Trip | **one-to-many** | a user owns many trips; a trip belongs to one user |
| Country → Trip, Trip → Day | **one-to-many** | a country has many trips; a trip has a day for every date |
| Day ↔ Place (through Visit) | **many-to-many** | a day has many places; the same place can be planned in many days of many trips |

| Model | Fields | Notes |
|---|---|---|
| **User** | `username`, `email`, `password` (hash), `date_joined` | custom user model (`AbstractUser`) |
| **Profile** | `user`, `home_city`, `bio`, `updated_at` | created at sign-up |
| **Country** | `code` (ISO, unique), `name`, `visa_free`, `visa_free_days` | created automatically from the geocoder |
| **Trip** | `owner`, `title`, `city`, `country`, `latitude`, `longitude`, `start_date`, `end_date`, `created_at` | coordinates and country are found by the server |
| **Day** | `trip`, `date`, `note`, cached weather | unique `(trip, date)` |
| **Place** | `name`, `address`, `latitude`, `longitude`, `category`, `osm_id` (unique), `created_at` | a real place, shared by all trips |
| **Visit** | `day`, `place`, `time`, `visited`, `created_at` | a place planned for a day; unique `(day, place)` |

## API endpoints

Full interactive documentation: http://localhost:8080/api/docs/ (generated from the code by drf-spectacular; schema at `/api/schema/` and [`docs/openapi.yaml`](docs/openapi.yaml)).

🔒 = needs `Authorization: Bearer <token>`. Without it the response is `401`.

**Trips**

| Method | Endpoint | Description | Responses |
|---|---|---|---|
| GET 🔒 | `/api/trips/` | My trips sorted by start date | 200, 401 |
| POST 🔒 | `/api/trips/` | Create a trip (`city`, `start_date`, `end_date`, optional `title`) | 201, 400, 401, 503 |
| GET 🔒 | `/api/trips/{id}/` | One of my trips | 200, 401, 404 |
| PUT / PATCH 🔒 | `/api/trips/{id}/` | Full / partial update; days are re-synced if the dates change | 200, 400, 401, 404, 503 |
| DELETE 🔒 | `/api/trips/{id}/` | Delete a trip with its days and visits | 204, 401, 404 |
| GET 🔒 | `/api/trips/{id}/days/` | Days with visits and weather | 200, 401, 404 |
| GET 🔒 | `/api/trips/{id}/places/` | Places planned in the trip | 200, 401, 404 |
| GET 🔒 | `/api/trips/{id}/stats/` | Statistics: days, visits, visited %, rainy days, by category, by day | 200, 401, 404 |
| POST 🔒 | `/api/trips/{id}/copy/` | Copy the trip to new dates: `{"start_date": "2027-03-01"}` | 201, 400, 401, 404 |
| GET 🔒 | `/api/dates/{YYYY-MM-DD}/trips/` | My trips that go on this date | 200, 400, 401 |
| GET 🔒 | `/api/cities/` | My cities with the number of trips | 200, 401 |

**Days and visits**

| Method | Endpoint | Description | Responses |
|---|---|---|---|
| GET 🔒 | `/api/days/{id}/` | One day with weather and visits | 200, 401, 404 |
| PUT / PATCH 🔒 | `/api/days/{id}/` | Change the day's note | 200, 400, 401, 404 |
| GET 🔒 | `/api/days/{id}/visits/` | The plan of the day | 200, 401, 404 |
| POST 🔒 | `/api/days/{id}/visits/` | Add a place: existing `{"place": 7}`, a suggestion (`name`, `latitude`, `longitude`, `osm_id`), new by name or by coordinates | 201, 400, 401, 404, 503 |
| GET 🔒 | `/api/days/{id}/places/` | Places of the day (many-to-many) | 200, 401, 404 |
| GET 🔒 | `/api/visits/` | All my visits | 200, 401 |
| GET 🔒 | `/api/visits/{id}/` | One visit | 200, 401, 404 |
| PUT / PATCH 🔒 | `/api/visits/{id}/` | Mark visited, change time, move to another day of the same trip | 200, 400, 401, 404 |
| DELETE 🔒 | `/api/visits/{id}/` | Remove the place from the day (the place stays in the catalog) | 204, 401, 404 |

**Places (shared catalog)**

| Method | Endpoint | Description | Responses |
|---|---|---|---|
| GET | `/api/places/` | All places (public) | 200 |
| GET | `/api/places/popular/` | Places planned in the most trips (public) | 200, 400 |
| GET 🔒 | `/api/places/suggest/?q=` | Autocomplete near the trip's city (Photon) | 200, 400, 401, 503 |
| GET | `/api/places/{id}/` | One place (public) | 200, 404 |
| PUT / PATCH 🔒 | `/api/places/{id}/` | Rename, change category or coordinates | 200, 400, 401, 404 |
| DELETE 🔒 | `/api/places/{id}/` | Delete a place that is not planned anywhere | 204, 401, 404, 409 |
| GET 🔒 | `/api/places/{id}/trips/` | My trips that visit this place | 200, 401, 404 |
| GET 🔒 | `/api/places/{id}/days/` | My days when this place is planned | 200, 401, 404 |

**Countries**

| Method | Endpoint | Description | Responses |
|---|---|---|---|
| GET | `/api/countries/` | Countries (public); for a logged-in user with the number of their trips | 200 |
| GET | `/api/countries/{id}/` | One country (public) | 200, 404 |
| PATCH 🔒 | `/api/countries/{id}/` | Set visa info: `{"visa_free": true, "visa_free_days": 30}` | 200, 400, 401, 404 |
| GET 🔒 | `/api/countries/{id}/trips/` | My trips to this country | 200, 401, 404 |
| GET 🔒 | `/api/countries/{id}/places/` | Places of my trips to this country | 200, 401, 404 |

**Service**

| Method | Endpoint | Description | Responses |
|---|---|---|---|
| GET 🔒 | `/api/geocode/?q=` | Preview a place search (nothing is saved) | 200, 400, 401, 503 |
| GET | `/api/health/` | Backend and database status (public) | 200, 503 |

### Request and response examples

Sign up:

```http
POST /api/auth/register/
Content-Type: application/json

{"username": "aruzhan", "password": "<your password>", "email": "aruzhan@example.com"}
```

`201 Created`

```json
{"user": {"id": 11, "username": "aruzhan", "email": "aruzhan@example.com", "date_joined": "2026-11-27T14:30:00+05:00",
          "profile": {"home_city": "", "bio": "", "updated_at": "2026-11-27T14:30:00+05:00"}, "trips_count": 0},
 "access": "eyJhbGciOi...", "refresh": "eyJhbGciOi..."}
```

Log in and use the token:

```http
POST /api/auth/login/
{"username": "demo", "password": "TripPlanner2026!"}
→ 200 {"access": "eyJ...", "refresh": "eyJ..."}

GET /api/trips/
Authorization: Bearer eyJ...
→ 200 [ ...only the trips of "demo"... ]
```

Create a trip:

```http
POST /api/trips/
Authorization: Bearer eyJ...
Content-Type: application/json

{"city": "Istanbul", "start_date": "2026-12-20", "end_date": "2026-12-23", "title": "Istanbul with friends"}
```

`201 Created`

```json
{"id": 16, "title": "Istanbul with friends", "city": "Istanbul", "owner": "demo",
 "country": {"id": 1, "code": "TR", "name": "Turkey", "visa_free": true},
 "latitude": 41.006381, "longitude": 28.9758715, "start_date": "2026-12-20", "end_date": "2026-12-23",
 "places_count": 0, "created_at": "2026-11-27T14:30:00+05:00"}
```

Update the profile and change the password:

```http
PATCH /api/auth/me/
{"username": "demo_traveler", "profile": {"home_city": "Almaty"}}
→ 200 (updated user)

POST /api/auth/change-password/
{"old_password": "...", "new_password": "..."}
→ 200 {"detail": "Password changed."}
```

Errors:

```json
GET /api/trips/                         (no token)
→ 401 {"detail": "Authentication credentials were not provided."}

POST /api/auth/login/                   (wrong password)
→ 401 {"detail": "No active account found with the given credentials"}

GET /api/trips/3/                       (trip of another user)
→ 404 {"detail": "No Trip matches the given query."}

POST /api/auth/register/                (username taken, weak password)
→ 400 {"username": ["A user with that username already exists."], "password": ["This password is too common."]}

POST /api/trips/  {"city": "Istanbul", "start_date": "2026-12-13", "end_date": "2026-12-10"}
→ 400 {"end_date": ["End date can't be before start date."]}
```

**Status codes:**
- `400` — invalid data (validation errors are returned per field);
- `401` — no token, invalid or expired token, wrong login or password;
- `404` — object not found or belongs to another user;
- `405` — method not allowed (e.g. `DELETE /api/days/{id}/`);
- `409` — a place that is planned in some day can't be deleted;
- `503` — external service (Nominatim / Photon / Open-Meteo) or the database is unavailable.

## Postman

Collection: [`postman/TripPlanner.postman_collection.json`](postman/TripPlanner.postman_collection.json) — 123 requests, 196 tests, covering all endpoints, authentication and error cases.

| Folder | What it checks |
|---|---|
| 0. Auth | sign up, taken username / weak password (400), log in, wrong password (401), refresh, broken token (401), me, update profile and username, change password, log in with the old (401) and the new password |
| 1. Trips | list, create two trips (owner = logged-in user), get, PUT, PATCH, days with weather |
| 2. Days | get, note (PATCH / PUT) |
| 3. Visits | add by name / existing place / coordinates, plan of a day, places of a day, mark visited, move, PUT, delete |
| 4. Places | catalog, search, places of a trip, trips and days of a place, PATCH, delete, popular places |
| 5. Countries | list, get, mark visa-free, trips and places of a country |
| 6. Trip filters | visa-free, country + city, date, period, search, status, ordering |
| 7. Stats, copy, cities | statistics, copy a trip, cities |
| 8. Validation & errors | 400, 404, 405, 409 cases |
| 9. Service | place suggestions (autocomplete), health check, geocode preview |
| 10. Access control | public GETs without a token (200), guest writes (401), a second user can't see, change or delete the first user's trip (404) |
| 11. Cleanup | delete the trips and the copy |

1. Start the app: `docker compose up -d --build`
2. In Postman: **Import** → select the collection file.
3. Right-click the collection → **Run collection** → set a delay of **1000 ms** (Nominatim allows 1 request per second) → **Run**.

How authentication works in the collection:
- The collection has **Auth → Bearer Token = `{{accessToken}}`**, so every request inherits the token.
- `0. Auth` creates a new user for every run (`traveler_<timestamp>`) and saves `accessToken` / `refreshToken` to collection variables.
- Public and guest requests use **No Auth**; the second-user requests use `{{otherAccessToken}}`.

IDs of created objects are saved automatically, every request has tests, and the collection deletes the trips it created, so it can be run many times, on an empty database or next to demo data. (The test users stay in the database: there is no endpoint for deleting a user.)

## Project structure

```
├── compose.yaml                         # db, backend, frontend
├── .env.example
├── docs/openapi.yaml                    # API documentation (OpenAPI 3)
├── postman/TripPlanner.postman_collection.json
├── backend/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── requirements.txt
│   ├── config/                          # settings (DRF, JWT), root URLs
│   └── trips/
│       ├── models.py                    # User, Profile, Country, Trip, Day, Place, Visit
│       ├── serializers.py               # trips, days, places, visits
│       ├── auth_serializers.py          # register, user + profile, change password
│       ├── auth_views.py                # register, me, change password
│       ├── views.py                     # API endpoints (per-user querysets)
│       ├── filters.py                   # query parameter helpers
│       ├── services.py                  # Nominatim, Photon, Open-Meteo
│       ├── urls.py
│       ├── admin.py
│       └── management/commands/seed_demo.py   # demo data
└── frontend/
    ├── Dockerfile                       # node build → nginx
    ├── nginx.conf                       # SPA + proxy /api to the backend
    ├── vite.config.js
    └── src/
        ├── main.jsx, App.jsx            # router, header, routes
        ├── api.js                       # fetch wrapper: Bearer token, refresh on 401
        ├── auth/                        # AuthProvider, useAuth, ProtectedRoute, tokens
        ├── pages/                       # Home, Login, Trips, TripForm, Trip, Profile
        ├── components/                  # map, place search, visits, modal, dialogs
        ├── hooks/                       # useApi, useDebounced
        └── index.css                    # dark theme
```
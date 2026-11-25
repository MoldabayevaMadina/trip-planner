"""
Integrations with external services. Only the backend talks to them;
the browser talks only to our own API.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import groupby

import requests
from django.conf import settings
from django.utils import timezone

from .models import Day, Trip

FORECAST_DAYS = 15  # Open-Meteo gives a daily forecast about two weeks ahead

class ExternalServiceError(Exception):
    """The external service did not answer (timeout, network error, 5xx)."""


@dataclass
class GeoResult:
    latitude: float
    longitude: float
    name: str
    address: str
    country: str
    country_code: str  
    osm_id: str 


def geocode(query: str) -> GeoResult | None:
    """Find coordinates for a text like "Almaty" or "Galata Tower, Istanbul". None if nothing found."""
    try:
        response = requests.get(
            settings.GEOCODER_URL,
            params={"q": query, "format": "jsonv2", "limit": 1, "addressdetails": 1, "accept-language": "en"},
            headers={"User-Agent": settings.GEOCODER_USER_AGENT},
            timeout=settings.HTTP_TIMEOUT,
        )
        response.raise_for_status()
        results = response.json()
    except (requests.RequestException, ValueError) as err:
        raise ExternalServiceError(f"Geocoding service unavailable: {err}") from err

    if not results:
        return None
    first = results[0]
    address = first.get("address") or {}
    osm_type, osm_number = first.get("osm_type"), first.get("osm_id")
    return GeoResult(
        latitude=float(first["lat"]),
        longitude=float(first["lon"]),
        name=first.get("name") or query,
        address=first.get("display_name", ""),
        country=address.get("country", ""),
        country_code=(address.get("country_code") or "").upper(),
        osm_id=f"{osm_type}/{osm_number}" if osm_type and osm_number else "",
    )

PHOTON_OSM_TYPES = {"N": "node", "W": "way", "R": "relation"}


def suggest_places(query: str, lat: float | None = None, lon: float | None = None, limit: int = 8) -> list[GeoResult]:
    """
    Search-as-you-type with Photon (OpenStreetMap data, made for autocomplete;
    Nominatim's usage policy does not allow it). Results near lat/lon come first.
    """
    params = {"q": query, "limit": limit, "lang": "en"}
    if lat is not None and lon is not None:
        params.update(lat=lat, lon=lon)
    try:
        response = requests.get(
            settings.PHOTON_URL,
            params=params,
            headers={"User-Agent": settings.GEOCODER_USER_AGENT},
            timeout=settings.HTTP_TIMEOUT,
        )
        response.raise_for_status()
        features = response.json().get("features", [])
    except (requests.RequestException, ValueError) as err:
        raise ExternalServiceError(f"Place search unavailable: {err}") from err

    results = []
    for feature in features:
        props = feature.get("properties") or {}
        coordinates = (feature.get("geometry") or {}).get("coordinates") or []
        if len(coordinates) != 2:
            continue
        lon_, lat_ = coordinates                       # GeoJSON order: longitude first
        osm_type = PHOTON_OSM_TYPES.get(props.get("osm_type"))
        osm_number = props.get("osm_id")
        street = " ".join(filter(None, [props.get("street"), props.get("housenumber")]))
        address = ", ".join(filter(None, [street, props.get("district"), props.get("city"), props.get("country")]))
        results.append(GeoResult(
            latitude=float(lat_),
            longitude=float(lon_),
            name=props.get("name") or street or query,
            address=address,
            country=props.get("country", ""),
            country_code=(props.get("countrycode") or "").upper(),
            # the same format as Nominatim ("way/24589121"), so both find the same place in our catalog
            osm_id=f"{osm_type}/{osm_number}" if osm_type and osm_number else "",
        ))
    return results


def _one_year_back(d: date) -> date:
    try:
        return d.replace(year=d.year - 1)
    except ValueError:  # 29 February -> 28 February
        return d.replace(year=d.year - 1, day=28)


def _plan(day_date: date, today: date) -> tuple[str, date]:
    """Decide where the weather for a day comes from, and which date to ask for."""
    if day_date < today:
        return Day.WeatherSource.ACTUAL, day_date
    if day_date <= today + timedelta(days=FORECAST_DAYS):
        return Day.WeatherSource.FORECAST, day_date
    return Day.WeatherSource.LAST_YEAR, _one_year_back(day_date)


def _fetch_daily(url: str, lat: float, lon: float, start: date, end: date) -> dict:
    """Ask Open-Meteo for daily weather. Returns {date: (code, max_temp, min_temp)}."""
    try:
        response = requests.get(
            url,
            params={
                "latitude": lat, "longitude": lon,
                "daily": "weather_code,temperature_2m_max,temperature_2m_min",
                "start_date": start.isoformat(), "end_date": end.isoformat(),
                "timezone": "auto",
            },
            timeout=settings.HTTP_TIMEOUT,
        )
        response.raise_for_status()
        daily = response.json()["daily"]
    except (requests.RequestException, ValueError, KeyError) as err:
        raise ExternalServiceError(f"Weather service unavailable: {err}") from err

    return {
        date.fromisoformat(d): (code, tmax, tmin)
        for d, code, tmax, tmin in zip(
            daily["time"], daily["weather_code"], daily["temperature_2m_max"], daily["temperature_2m_min"]
        )
    }


def refresh_weather(trip: Trip) -> bool:
    """
    Fill the weather cache of every day of the trip.
    Returns False if the weather service failed (the trip still works, just without weather).
    """
    now = timezone.now()
    fresh_after = now - timedelta(minutes=settings.WEATHER_CACHE_MINUTES)
    today = timezone.localdate()

    days = list(trip.days.all())
    plans = {day.id: _plan(day.date, today) for day in days}
    stale = [
        d for d in days
        if d.weather_updated_at is None
        or d.weather_updated_at < fresh_after
        or d.weather_source != plans[d.id][0]
    ]
    if not stale:
        return True

    ok = True
    stale.sort(key=lambda d: plans[d.id][0])
    for source, group in groupby(stale, key=lambda d: plans[d.id][0]):
        group = list(group)
        query_dates = [plans[d.id][1] for d in group]
        url = settings.WEATHER_FORECAST_URL if source == Day.WeatherSource.FORECAST else settings.WEATHER_ARCHIVE_URL
        try:
            data = _fetch_daily(url, trip.latitude, trip.longitude, min(query_dates), max(query_dates))
        except ExternalServiceError:
            ok = False
            continue
        for day in group:
            code, tmax, tmin = data.get(plans[day.id][1], (None, None, None))
            day.weather_code, day.temp_max, day.temp_min = code, tmax, tmin
            day.weather_source = source
            day.weather_updated_at = now
        Day.objects.bulk_update(group, ["weather_code", "temp_max", "temp_min", "weather_source", "weather_updated_at"])
    return ok



WEATHER_CODES = {
    0: ("☀️", "Clear"), 1: ("🌤", "Mostly clear"), 2: ("⛅", "Partly cloudy"), 3: ("☁️", "Overcast"),
    45: ("🌫", "Fog"), 48: ("🌫", "Fog"),
    51: ("🌦", "Drizzle"), 53: ("🌦", "Drizzle"), 55: ("🌦", "Drizzle"),
    61: ("🌧", "Light rain"), 63: ("🌧", "Rain"), 65: ("🌧", "Heavy rain"),
    71: ("🌨", "Light snow"), 73: ("🌨", "Snow"), 75: ("❄️", "Heavy snow"),
    80: ("🌦", "Showers"), 81: ("🌧", "Showers"), 82: ("⛈", "Violent showers"),
    95: ("⛈", "Thunderstorm"), 96: ("⛈", "Thunderstorm with hail"), 99: ("⛈", "Thunderstorm with hail"),
}


def describe_weather(code):
    if code is None:
        return "", ""
    return WEATHER_CODES.get(code, ("🌡", "Unknown"))


def is_rainy(code):
    return code is not None and code >= 51
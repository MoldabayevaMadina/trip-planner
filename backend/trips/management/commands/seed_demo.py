from datetime import time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from trips.models import Country, Place, Trip, Visit

S, M, F, W, SH, O = "sight", "museum", "food", "walk", "shopping", "other"

COUNTRIES = {
    "TR": ("Turkey", True, 30),
    "GE": ("Georgia", True, 365),
    "AE": ("United Arab Emirates", True, 30),
    "FR": ("France", False, None),
    "JP": ("Japan", False, None),
}

PLACES = {
    "hagia": ("Hagia Sophia", M, 41.0086, 28.9802, "Sultanahmet, Fatih, Istanbul, Turkey"),
    "galata": ("Galata Tower", S, 41.0256, 28.9741, "Beyoğlu, Istanbul, Turkey"),
    "bazaar": ("Grand Bazaar", SH, 41.0107, 28.9681, "Beyazıt, Fatih, Istanbul, Turkey"),
    "eminonu": ("Balık ekmek in Eminönü", F, 41.0172, 28.9707, "Eminönü, Fatih, Istanbul, Turkey"),
    "topkapi": ("Topkapı Palace", M, 41.0115, 28.9834, "Cankurtaran, Fatih, Istanbul, Turkey"),
    "narikala": ("Narikala Fortress", S, 41.6880, 44.8086, "Old Tbilisi, Tbilisi, Georgia"),
    "baths": ("Sulfur baths (Abanotubani)", O, 41.6880, 44.8110, "Abanotubani, Tbilisi, Georgia"),
    "drybridge": ("Dry Bridge Market", SH, 41.6990, 44.8040, "Dry Bridge, Tbilisi, Georgia"),
    "rustaveli": ("Rustaveli Avenue", W, 41.7008, 44.7940, "Rustaveli Avenue, Tbilisi, Georgia"),
    "burj": ("Burj Khalifa", S, 25.1972, 55.2744, "Downtown Dubai, Dubai, United Arab Emirates"),
    "mall": ("The Dubai Mall", SH, 25.1985, 55.2796, "Downtown Dubai, Dubai, United Arab Emirates"),
    "future": ("Museum of the Future", M, 25.2193, 55.2820, "Sheikh Zayed Road, Dubai, United Arab Emirates"),
    "marina": ("Dubai Marina Walk", W, 25.0805, 55.1403, "Dubai Marina, Dubai, United Arab Emirates"),
    "eiffel": ("Eiffel Tower", S, 48.8584, 2.2945, "Champ de Mars, Paris, France"),
    "louvre": ("Louvre Museum", M, 48.8606, 2.3376, "Rue de Rivoli, Paris, France"),
    "montmartre": ("Montmartre", W, 48.8867, 2.3431, "Montmartre, Paris, France"),
    "flore": ("Café de Flore", F, 48.8541, 2.3326, "Saint-Germain-des-Prés, Paris, France"),
    "sensoji": ("Senso-ji Temple", S, 35.7148, 139.7967, "Asakusa, Taito, Tokyo, Japan"),
    "shibuya": ("Shibuya Crossing", W, 35.6595, 139.7005, "Shibuya, Tokyo, Japan"),
    "tsukiji": ("Tsukiji Outer Market", F, 35.6655, 139.7707, "Tsukiji, Chuo, Tokyo, Japan"),
    "tnm": ("Tokyo National Museum", M, 35.7188, 139.7765, "Ueno Park, Taito, Tokyo, Japan"),
}

TRIPS = [
    dict(title="Istanbul in autumn", city="Istanbul", country="TR", lat=41.0082, lon=28.9784, start=-40, length=4,
         notes={0: "Old city & museums"},
         plan=[[("hagia", "10:00", True), ("bazaar", "14:00", True), ("eminonu", "18:30", True)],
               [("galata", "11:00", True), ("topkapi", "15:00", False)],
               [], []]),
    dict(title="Tbilisi weekend", city="Tbilisi", country="GE", lat=41.7151, lon=44.8271, start=-1, length=4,
         notes={1: "Sulfur baths in the evening"},
         plan=[[("narikala", "11:00", True), ("rustaveli", "17:00", True)],
               [("drybridge", "12:00", False), ("baths", "19:00", False)],
               [], []]),
    dict(title="Dubai with family", city="Dubai", country="AE", lat=25.2048, lon=55.2708, start=14, length=5,
         notes={0: "Arrival day, take it easy"},
         plan=[[("marina", "19:00", False)],
               [("burj", "10:00", False), ("mall", "13:00", False)],
               [("future", "11:00", False)],
               [], []]),
    dict(title="Istanbul again", city="Istanbul", country="TR", lat=41.0082, lon=28.9784, start=30, length=3,
         notes={},
         plan=[[("galata", "10:00", False), ("eminonu", None, False)],
               [("hagia", "09:30", False)],
               []]),
    dict(title="Paris in winter", city="Paris", country="FR", lat=48.8566, lon=2.3522, start=60, length=5,
         notes={1: "Museum day"},
         plan=[[("eiffel", "18:00", False)],
               [("louvre", "10:00", False), ("flore", "16:00", False)],
               [("montmartre", "11:00", False)],
               [], []]),
    dict(title="Tokyo in spring", city="Tokyo", country="JP", lat=35.6762, lon=139.6503, start=120, length=7,
         notes={0: "Jet lag: short walk only"},
         plan=[[("shibuya", "20:00", False)],
               [("sensoji", "09:00", False), ("tnm", "14:00", False)],
               [("tsukiji", "08:00", False)],
               [], [], [], []]),
]


class Command(BaseCommand):
    help = "Fill the database with demo trips, places, visits and countries."

    @transaction.atomic
    def handle(self, *args, **options):
        countries = {}
        for code, (name, visa_free, days) in COUNTRIES.items():
            country, _ = Country.objects.get_or_create(code=code, defaults={"name": name})
            country.visa_free, country.visa_free_days = visa_free, days
            country.save(update_fields=["visa_free", "visa_free_days"])
            countries[code] = country

        places = {}
        for key, (name, category, lat, lon, address) in PLACES.items():
            places[key], _ = Place.objects.get_or_create(
                name=name, latitude=lat, longitude=lon,
                defaults={"category": category, "address": address},
            )

        today = timezone.localdate()
        created = 0
        for t in TRIPS:
            if Trip.objects.filter(title=t["title"]).exists():
                self.stdout.write(f"skip: {t['title']} (already exists)")
                continue
            start = today + timedelta(days=t["start"])
            trip = Trip.objects.create(
                title=t["title"], city=t["city"], country=countries[t["country"]],
                latitude=t["lat"], longitude=t["lon"],
                start_date=start, end_date=start + timedelta(days=t["length"] - 1),
            )
            trip.sync_days()
            days = list(trip.days.order_by("date"))
            for index, note in t["notes"].items():
                days[index].note = note
                days[index].save(update_fields=["note"])
            Visit.objects.bulk_create([
                Visit(day=day, place=places[key], visited=visited,
                      time=time.fromisoformat(at) if at else None)
                for day, plan in zip(days, t["plan"])
                for key, at, visited in plan
            ])
            created += 1
            self.stdout.write(f"created: {trip}")

        self.stdout.write(self.style.SUCCESS(
            f"Done: {created} new trips. Countries: {Country.objects.count()}, "
            f"places: {Place.objects.count()}, visits: {Visit.objects.count()}."
        ))
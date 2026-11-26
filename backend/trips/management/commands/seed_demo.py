"""
python manage.py seed_demo

Fills the database with demo data, at least 10 rows in every table of the app:
10 users with profiles, 12 countries, 40 places, 15 trips with their days and visits.

- The main demo account is "demo": it owns most trips (past, current and upcoming, two of them
  in Istanbul with shared places). Nine more travellers own one trip each.
- All demo users have the password from the DEMO_PASSWORD environment variable
  (default "TripPlanner2026!"). It is a demo password: never use it for real accounts.
- No external services are called: coordinates are written here. Dates are counted from today.
- Safe to run again: existing users, countries, places and trips (same owner and title) are skipped.
- Visa information is DEMO data, check official sources before a real trip.
"""
import os
from datetime import time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from trips.models import Country, Day, Place, Profile, Trip, User, Visit

S, M, F, W, SH, O = "sight", "museum", "food", "walk", "shopping", "other"

USERS = {
    # username: (first name, home city, bio)
    "demo": ("Demo", "Almaty", "The main demo account: most trips belong to me."),
    "aigerim": ("Aigerim", "Almaty", "Art and museums lover."),
    "daniyar": ("Daniyar", "Astana", "Football and street food."),
    "madina": ("Madina", "Shymkent", "K-pop and skincare shopping."),
    "timur": ("Timur", "Almaty", "History of the Silk Road."),
    "zhanna": ("Zhanna", "Karaganda", "Beaches and temples."),
    "arman": ("Arman", "Almaty", "Mountains every summer."),
    "dana": ("Dana", "Astana", "Techno, galleries and long walks."),
    "nurlan": ("Nurlan", "Aktobe", "First trip abroad."),
    "alina": ("Alina", "Pavlodar", "Wine regions and old towns."),
}

COUNTRIES = {
    # code: (name, visa_free, visa_free_days)
    "TR": ("Turkey", True, 30),
    "GE": ("Georgia", True, 365),
    "AE": ("United Arab Emirates", True, 30),
    "FR": ("France", False, None),
    "JP": ("Japan", False, None),
    "IT": ("Italy", False, None),
    "ES": ("Spain", False, None),
    "DE": ("Germany", False, None),
    "KR": ("South Korea", True, 30),
    "UZ": ("Uzbekistan", True, 30),
    "TH": ("Thailand", True, 30),
    "KG": ("Kyrgyzstan", True, 90),
}

PLACES = {
    # key: (name, category, latitude, longitude, address)
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
    "colosseum": ("Colosseum", S, 41.8902, 12.4922, "Piazza del Colosseo, Rome, Italy"),
    "trevi": ("Trevi Fountain", S, 41.9009, 12.4833, "Piazza di Trevi, Rome, Italy"),
    "vatican": ("Vatican Museums", M, 41.9065, 12.4536, "Viale Vaticano, Vatican City"),
    "trastevere": ("Dinner in Trastevere", F, 41.8890, 12.4700, "Trastevere, Rome, Italy"),
    "sagrada": ("Sagrada Família", S, 41.4036, 2.1744, "Carrer de Mallorca, Barcelona, Spain"),
    "guell": ("Park Güell", W, 41.4145, 2.1527, "Gràcia, Barcelona, Spain"),
    "boqueria": ("La Boqueria Market", F, 41.3818, 2.1716, "La Rambla, Barcelona, Spain"),
    "gyeongbok": ("Gyeongbokgung Palace", M, 37.5796, 126.9770, "Jongno-gu, Seoul, South Korea"),
    "myeongdong": ("Myeongdong Street", SH, 37.5636, 126.9827, "Jung-gu, Seoul, South Korea"),
    "namsan": ("N Seoul Tower", S, 37.5512, 126.9882, "Namsan, Yongsan-gu, Seoul, South Korea"),
    "registan": ("Registan Square", S, 39.6547, 66.9758, "Registan Street, Samarkand, Uzbekistan"),
    "shahizinda": ("Shah-i-Zinda", S, 39.6631, 66.9883, "Samarkand, Uzbekistan"),
    "siab": ("Siab Bazaar", F, 39.6620, 66.9815, "Tashkent Street, Samarkand, Uzbekistan"),
    "grandpalace": ("The Grand Palace", S, 13.7500, 100.4913, "Phra Nakhon, Bangkok, Thailand"),
    "watarun": ("Wat Arun", S, 13.7437, 100.4888, "Bangkok Yai, Bangkok, Thailand"),
    "chatuchak": ("Chatuchak Weekend Market", SH, 13.7999, 100.5500, "Chatuchak, Bangkok, Thailand"),
    "beach": ("Issyk-Kul beach", W, 42.6490, 77.0840, "Cholpon-Ata, Kyrgyzstan"),
    "petroglyphs": ("Petroglyphs open-air museum", M, 42.6580, 77.1190, "Cholpon-Ata, Kyrgyzstan"),
    "brandenburg": ("Brandenburg Gate", S, 52.5163, 13.3777, "Pariser Platz, Berlin, Germany"),
}

# owner, start (days from today), length in days; plan: one list per day of (place, "HH:MM" or None, visited)
TRIPS = [
    # ---------- the main demo account ----------
    dict(owner="demo", title="Istanbul in autumn", city="Istanbul", country="TR", lat=41.0082, lon=28.9784,
         start=-40, length=4, notes={0: "Old city & museums"},
         plan=[[("hagia", "10:00", True), ("bazaar", "14:00", True), ("eminonu", "18:30", True)],
               [("galata", "11:00", True), ("topkapi", "15:00", False)], [], []]),
    dict(owner="demo", title="Tbilisi weekend", city="Tbilisi", country="GE", lat=41.7151, lon=44.8271,
         start=-1, length=4, notes={1: "Sulfur baths in the evening"},
         plan=[[("narikala", "11:00", True), ("rustaveli", "17:00", True)],
               [("drybridge", "12:00", False), ("baths", "19:00", False)], [], []]),
    dict(owner="demo", title="Dubai with family", city="Dubai", country="AE", lat=25.2048, lon=55.2708,
         start=14, length=5, notes={0: "Arrival day, take it easy"},
         plan=[[("marina", "19:00", False)], [("burj", "10:00", False), ("mall", "13:00", False)],
               [("future", "11:00", False)], [], []]),
    dict(owner="demo", title="Istanbul again", city="Istanbul", country="TR", lat=41.0082, lon=28.9784,
         start=30, length=3, notes={},
         plan=[[("galata", "10:00", False), ("eminonu", None, False)], [("hagia", "09:30", False)], []]),
    dict(owner="demo", title="Paris in winter", city="Paris", country="FR", lat=48.8566, lon=2.3522,
         start=60, length=5, notes={1: "Museum day"},
         plan=[[("eiffel", "18:00", False)], [("louvre", "10:00", False), ("flore", "16:00", False)],
               [("montmartre", "11:00", False)], [], []]),
    dict(owner="demo", title="Tokyo in spring", city="Tokyo", country="JP", lat=35.6762, lon=139.6503,
         start=120, length=7, notes={0: "Jet lag: short walk only"},
         plan=[[("shibuya", "20:00", False)], [("sensoji", "09:00", False), ("tnm", "14:00", False)],
               [("tsukiji", "08:00", False)], [], [], [], []]),
    # ---------- other travellers: one trip each ----------
    dict(owner="aigerim", title="Roman holiday", city="Rome", country="IT", lat=41.9028, lon=12.4964,
         start=45, length=4, notes={1: "Book the Vatican online"},
         plan=[[("colosseum", "10:00", False), ("trevi", "18:00", False)],
               [("vatican", "09:00", False), ("trastevere", "20:00", False)], [], []]),
    dict(owner="daniyar", title="Barcelona with friends", city="Barcelona", country="ES", lat=41.3874, lon=2.1686,
         start=-20, length=3, notes={},
         plan=[[("sagrada", "11:00", True), ("boqueria", "14:00", True)], [("guell", "10:00", True)], []]),
    dict(owner="madina", title="Seoul shopping trip", city="Seoul", country="KR", lat=37.5665, lon=126.9780,
         start=25, length=5, notes={0: "Buy a T-money card"},
         plan=[[("myeongdong", "15:00", False)], [("gyeongbok", "10:00", False), ("namsan", "19:00", False)],
               [], [], []]),
    dict(owner="timur", title="Samarkand and the Silk Road", city="Samarkand", country="UZ", lat=39.6270, lon=66.9750,
         start=-70, length=3, notes={},
         plan=[[("registan", "09:00", True), ("siab", "13:00", True)], [("shahizinda", "10:00", True)], []]),
    dict(owner="zhanna", title="Bangkok temples", city="Bangkok", country="TH", lat=13.7563, lon=100.5018,
         start=90, length=6, notes={2: "Weekend market"},
         plan=[[("grandpalace", "09:00", False)], [("watarun", "16:00", False)], [("chatuchak", "10:00", False)],
               [], [], []]),
    dict(owner="arman", title="Issyk-Kul summer", city="Cholpon-Ata", country="KG", lat=42.6491, lon=77.0827,
         start=200, length=5, notes={},
         plan=[[("beach", None, False)], [("petroglyphs", "11:00", False)], [], [], []]),
    dict(owner="dana", title="Berlin weekend", city="Berlin", country="DE", lat=52.5200, lon=13.4050,
         start=8, length=3, notes={},
         plan=[[("brandenburg", "12:00", False)], [], []]),
    dict(owner="nurlan", title="First time in Istanbul", city="Istanbul", country="TR", lat=41.0082, lon=28.9784,
         start=-10, length=3, notes={},
         plan=[[("galata", "10:00", True), ("hagia", "14:00", True)], [("bazaar", "11:00", False)], []]),
    dict(owner="alina", title="Georgian old towns", city="Tbilisi", country="GE", lat=41.7151, lon=44.8271,
         start=150, length=4, notes={},
         plan=[[("narikala", "10:00", False)], [("rustaveli", "18:00", False)], [], []]),
]


class Command(BaseCommand):
    help = "Fill the database with demo data: at least 10 rows in every table."

    @transaction.atomic
    def handle(self, *args, **options):
        password = os.environ.get("DEMO_PASSWORD", "TripPlanner2026!")

        users = {}
        for username, (first_name, home_city, bio) in USERS.items():
            user, created = User.objects.get_or_create(username=username, defaults={
                "first_name": first_name, "email": f"{username}@example.com"})
            if created:
                user.set_password(password)     # stored as a hash
                user.save()
            Profile.objects.get_or_create(user=user, defaults={"home_city": home_city, "bio": bio})
            users[username] = user

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
            owner = users[t["owner"]]
            if Trip.objects.filter(owner=owner, title=t["title"]).exists():
                continue
            start = today + timedelta(days=t["start"])
            trip = Trip.objects.create(
                owner=owner, title=t["title"], city=t["city"], country=countries[t["country"]],
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
            self.stdout.write(f"created: {trip.title} ({owner.username})")

        self.stdout.write(self.style.SUCCESS(
            f"Done: {created} new trips. Rows now — users: {User.objects.count()}, "
            f"profiles: {Profile.objects.count()}, countries: {Country.objects.count()}, "
            f"trips: {Trip.objects.count()}, days: {Day.objects.count()}, "
            f"places: {Place.objects.count()}, visits: {Visit.objects.count()}."
        ))
        self.stdout.write(f'Log in as "demo" (or any demo user) with the password "{password}".')
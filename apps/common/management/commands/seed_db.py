from datetime import date, time, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.users.models import User, UserProfile, Roles
from apps.members.models import Department, Location, Members
from apps.attendance.models import AttendanceSession, AttendanceRecord


class Command(BaseCommand):
    help = "Seeds the database with church staff, departments, locations, congregants, and attendance records."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting church database seeding..."))
        DEFAULT_PASSWORD = "ChurchPass2026!"

        # -------------------------------------------------------------
        # 1. SEED SYSTEM STAFF USERS (PORTAL ACCOUNTS)
        # -------------------------------------------------------------
        staff_data = [
            {
                "email": "admin@church.org",
                "first_name": "David",
                "last_name": "Osei",
                "phone_number": "+233240000001",
                "role": Roles.ADMIN,
                "is_staff": True,
                "is_superuser": True,
                "dob": date(1985, 4, 12),
                "location": "Main Campus Administration",
            },
            {
                "email": "pastor.john@church.org",
                "first_name": "Rev. John",
                "last_name": "Mensah",
                "phone_number": "+233240000002",
                "role": Roles.PASTOR,
                "is_staff": False,
                "is_superuser": False,
                "dob": date(1978, 9, 23),
                "location": "Pastoral Office",
            },
            {
                "email": "usher.sarah@church.org",
                "first_name": "Sarah",
                "last_name": "Boateng",
                "phone_number": "+233240000003",
                "role": Roles.USHER,
                "is_staff": False,
                "is_superuser": False,
                "dob": date(1996, 6, 18),
                "location": "Sanctuary Entrance Desk",
            },
            {
                "email": "usher.brother@church.org",
                "first_name": "Joseph",
                "last_name": "Appiah",
                "phone_number": "+233240000004",
                "role": Roles.USHER,
                "is_staff": False,
                "is_superuser": False,
                "dob": date(1994, 11, 5),
                "location": "Gallery & Overflow Desk",
            },
            {
                "email": "staff.mary@church.org",
                "first_name": "Mary",
                "last_name": "Afriyie",
                "phone_number": "+233240000005",
                "role": Roles.STAFF,
                "is_staff": False,
                "is_superuser": False,
                "dob": date(1992, 1, 30),
                "location": "Secretariat Office",
            },
        ]

        seeded_users = []
        for s in staff_data:
            user, created = User.objects.get_or_create(
                email=s["email"],
                defaults={
                    "first_name": s["first_name"],
                    "last_name": s["last_name"],
                    "phone_number": s["phone_number"],
                    "role": s["role"],
                    "is_staff": s["is_staff"],
                    "is_superuser": s["is_superuser"],
                    "is_active": True,
                }
            )
            # Ensure password and role are updated
            user.set_password(DEFAULT_PASSWORD)
            user.first_name = s["first_name"]
            user.last_name = s["last_name"]
            user.phone_number = s["phone_number"]
            user.role = s["role"]
            user.is_staff = s["is_staff"]
            user.is_superuser = s["is_superuser"]
            user.save()

            UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    "date_of_birth": s["dob"],
                    "location": s["location"],
                }
            )
            seeded_users.append(user)

        self.stdout.write(self.style.SUCCESS(f" Seeded {len(seeded_users)} Staff & Portal accounts."))

        # -------------------------------------------------------------
        # 2. SEED DEPARTMENTS
        # -------------------------------------------------------------
        departments_data = [
            ("Choir & Music Ministry", "Praise, worship leaders, instrumentalists, and technical sound engineers."),
            ("Ushering & Protocol", "Welcoming congregants, seat management, sanctuary order, and entrance check-ins."),
            ("Media & Technical Team", "Audio-visual production, live streaming, projection, and media documentation."),
            ("Youth & Young Adults", "Dynamic fellowship for high school, university students, and young professionals."),
            ("Children's Ministry", "Sunday school, foundational biblical teaching, and child safety."),
            ("Prayer & Intercession", "Weekly prayer chains, dawn intercession, and vigil mobilization."),
            ("Evangelism & Outreach", "Community missions, hospital visitation, and soul-winning outreaches."),
            ("Welfare & Hospitality", "First-time visitor hosting, member follow-up, and benevolence care."),
        ]

        dept_objs = {}
        for name, desc in departments_data:
            dept, _ = Department.objects.get_or_create(name=name, defaults={"description": desc})
            dept_objs[name] = dept

        self.stdout.write(self.style.SUCCESS(f" Seeded {len(dept_objs)} Church Departments."))

        # -------------------------------------------------------------
        # 3. SEED SANCTUARY LOCATIONS (GEOFENCING)
        # -------------------------------------------------------------
        locations_data = [
            {
                "name": "Main Auditorium (Central Sanctuary)",
                "latitude": 5.603716,
                "longitude": -0.186964,
                "radius": 150.0,
                "description": "Main auditorium seating 2,500 congregants with 150m perimeter geofence.",
            },
            {
                "name": "Youth & Overflow Chapel",
                "latitude": 5.604120,
                "longitude": -0.187420,
                "radius": 100.0,
                "description": "Multi-purpose youth hall and midweek service overflow center.",
            },
        ]

        loc_objs = []
        for l in locations_data:
            loc, _ = Location.objects.get_or_create(
                name=l["name"],
                defaults={
                    "latitude": l["latitude"],
                    "longitude": l["longitude"],
                    "radius": l["radius"],
                    "description": l["description"],
                }
            )
            loc_objs.append(loc)

        main_sanctuary = loc_objs[0]
        self.stdout.write(self.style.SUCCESS(f" Seeded {len(loc_objs)} Geofenced Church Locations."))

        # -------------------------------------------------------------
        # 4. SEED CONGREGANTS / MEMBERS (WHO DO NOT LOG IN)
        # -------------------------------------------------------------
        members_list = [
            ("Kwame Kwarteng", "kwame.kwarteng@gmail.com", "+233241110001", "Choir & Music Ministry", date(1995, 3, 14), "East Legon, Accra"),
            ("Abena Serwaa", "abena.serwaa@yahoo.com", "+233241110002", "Ushering & Protocol", date(1998, 8, 22), "Madina Estate, Accra"),
            ("Kofi Annan Jr.", "kofi.annan.jr@outlook.com", "+233241110003", "Media & Technical Team", date(1993, 12, 5), "Airport Residential, Accra"),
            ("Akosua Agyeman", "akosua.agyeman@gmail.com", "+233241110004", "Youth & Young Adults", date(2001, 7, 19), "Haatso, Accra"),
            ("Yaw Boakye", "yaw.boakye@hotmail.com", "+233241110005", "Prayer & Intercession", date(1988, 4, 11), "Adenta Barrier, Accra"),
            ("Ama Mansah", "ama.mansah@gmail.com", "+233241110006", "Welfare & Hospitality", date(1992, 10, 2), "Dzorwulu, Accra"),
            ("Emmanuel Tetteh", "emmanuel.tetteh@gmail.com", "+233241110007", "Choir & Music Ministry", date(1997, 1, 15), "Spintex Road, Accra"),
            ("Grace Ofori", "grace.ofori@yahoo.com", "+233241110008", "Children's Ministry", date(1990, 6, 28), "Osu, Accra"),
            ("Samuel Darko", "samuel.darko@gmail.com", "+233241110009", "Evangelism & Outreach", date(1986, 9, 17), "Tesano, Accra"),
            ("Priscilla Asare", "priscilla.asare@gmail.com", "+233241110010", "Ushering & Protocol", date(1999, 11, 23), "Achimota, Accra"),
            ("Daniel Quaye", "daniel.quaye@outlook.com", "+233241110011", "Media & Technical Team", date(1994, 5, 8), "Tema Community 6"),
            ("Eunice Bempong", "eunice.bempong@gmail.com", "+233241110012", "Welfare & Hospitality", date(1991, 2, 14), "Cantonments, Accra"),
            ("Michael Opoku", "michael.opoku@yahoo.com", "+233241110013", "Youth & Young Adults", date(2002, 4, 30), "Legon Campus, Accra"),
            ("Beatrice Addo", "beatrice.addo@gmail.com", "+233241110014", "Prayer & Intercession", date(1989, 7, 9), "Abelemkpe, Accra"),
            ("Peter Mensah", "peter.mensah@gmail.com", "+233241110015", "Evangelism & Outreach", date(1984, 12, 25), "Dome Pillar 2, Accra"),
        ]

        seeded_members = []
        for name, email, phone, dept_name, dob, addr in members_list:
            member, _ = Members.objects.get_or_create(
                email=email,
                defaults={
                    "name": name,
                    "phone_number": phone,
                    "department": dept_objs[dept_name],
                    "date_of_birth": dob,
                    "address": addr,
                }
            )
            # Ensure ID is generated
            if not member.member_id:
                member.save()
            seeded_members.append(member)

        self.stdout.write(self.style.SUCCESS(f" Seeded {len(seeded_members)} Congregants with Member IDs (FY-0001+)."))

        # -------------------------------------------------------------
        # 5. SEED ATTENDANCE SESSIONS (ACTIVE TODAY & HISTORICAL)
        # -------------------------------------------------------------
        today = timezone.localdate()
        sessions_plan = [
            {
                "title": "Sunday Celebration Service (Active)",
                "date": today,
                "start_time": time(8, 30),
                "end_time": time(11, 30),
                "is_active": True,
                "location": main_sanctuary,
            },
            {
                "title": "Midweek Prayer & Miracle Encounter",
                "date": today - timedelta(days=4),
                "start_time": time(18, 0),
                "end_time": time(20, 0),
                "is_active": False,
                "location": main_sanctuary,
            },
            {
                "title": "Sunday 1st Anointing Service",
                "date": today - timedelta(days=7),
                "start_time": time(8, 0),
                "end_time": time(10, 30),
                "is_active": False,
                "location": main_sanctuary,
            },
            {
                "title": "Sunday Covenant & Breakthrough Service",
                "date": today - timedelta(days=14),
                "start_time": time(8, 30),
                "end_time": time(11, 0),
                "is_active": False,
                "location": main_sanctuary,
            },
        ]

        seeded_sessions = []
        for sp in sessions_plan:
            session, _ = AttendanceSession.objects.get_or_create(
                title=sp["title"],
                date=sp["date"],
                defaults={
                    "start_time": sp["start_time"],
                    "end_time": sp["end_time"],
                    "is_active": sp["is_active"],
                    "location": sp["location"],
                }
            )
            session.is_active = sp["is_active"]
            session.save()
            seeded_sessions.append(session)

        self.stdout.write(self.style.SUCCESS(f" Seeded {len(seeded_sessions)} Attendance Sessions (including active service)."))

        # -------------------------------------------------------------
        # 6. SEED ATTENDANCE RECORDS (MIX OF QR SCANS & USHER DESK)
        # -------------------------------------------------------------
        record_count = 0
        for s_idx, session in enumerate(seeded_sessions):
            # Check in a subset of members for each session
            subset = seeded_members[:(10 + (s_idx * 2))]
            for m_idx, member in enumerate(subset):
                # Half QR scan with GPS, half Usher Desk manual check-in
                if m_idx % 2 == 0:
                    device = "Mobile QR Check-In (Safari on iOS)"
                    dist = 14.5 + (m_idx * 3.2)
                else:
                    device = "Usher Desk Manual Check-in"
                    dist = 2.0

                rec, created = AttendanceRecord.objects.get_or_create(
                    session=session,
                    member=member,
                    defaults={
                        "latitude": session.location.latitude,
                        "longitude": session.location.longitude,
                        "distance_meters": dist,
                        "status": "present",
                        "device_info": device,
                    }
                )
                if created:
                    record_count += 1

        self.stdout.write(self.style.SUCCESS(f" Seeded {record_count} new Attendance Records across services."))
        self.stdout.write(self.style.SUCCESS(" Database seeding complete!"))

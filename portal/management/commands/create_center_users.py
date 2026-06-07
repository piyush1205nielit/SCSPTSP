"""Create the 4 portal users:
  1) admin              -> Django superuser, sees all centers
  2) inderlok_admin     -> restricted to Inderlok
  3) karkardooma_admin  -> restricted to Karkardooma
  4) janakpuri_admin    -> restricted to Janakpuri

The default password for the 3 center users is 'Center@123'.
The admin password is 'Admin@123'.

Re-running the command updates passwords + center for existing users
(so you can rerun it to fix typos).
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from portal.models import UserProfile


CENTER_USERS = [
    {"username": "inderlok_admin", "center": "inderlok", "password": "Center@123"},
    {"username": "karkardooma_admin", "center": "karkardooma", "password": "Center@123"},
    {"username": "janakpuri_admin", "center": "janakpuri", "password": "Center@123"},
]

ADMIN_USER = {"username": "admin", "password": "Admin@123"}


class Command(BaseCommand):
    help = "Create/refresh the 4 portal users (1 admin + 3 center users)."

    def handle(self, *args, **options):
        admin, created = User.objects.get_or_create(
            username=ADMIN_USER["username"],
            defaults={"is_superuser": True, "is_staff": True, "email": ""},
        )
        admin.is_superuser = True
        admin.is_staff = True
        admin.set_password(ADMIN_USER["password"])
        admin.save()
        profile, _ = UserProfile.objects.get_or_create(user=admin)
        profile.center = None
        profile.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"  admin user '{admin.username}' (all centers) - "
                f"{'created' if created else 'updated'} - password: {ADMIN_USER['password']}"
            )
        )

        for u in CENTER_USERS:
            user, created = User.objects.get_or_create(
                username=u["username"],
                defaults={"is_superuser": False, "is_staff": False, "email": ""},
            )
            user.is_superuser = False
            user.is_staff = False
            user.set_password(u["password"])
            user.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.center = u["center"]
            profile.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"  center user '{user.username}' -> {u['center']} - "
                    f"{'created' if created else 'updated'} - password: {u['password']}"
                )
            )

        self.stdout.write(self.style.SUCCESS("All 4 users are ready."))

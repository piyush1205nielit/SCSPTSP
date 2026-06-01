"""
Recalculate the stored claimable_amount for every student in the database.

Run this after deploying the new claimable amount logic to backfill
existing rows (the old rows still have 0 because the old save() never
calculated it).
"""

from django.core.management.base import BaseCommand
from portal.models import studentdata


class Command(BaseCommand):
    help = "Recalculate claimable_amount for all existing students."

    def handle(self, *args, **options):
        total = studentdata.objects.count()
        updated = 0
        for s in studentdata.objects.iterator():
            old = s.claimable_amount
            new = s.calculate_claimable_amount()
            if old != new:
                s.claimable_amount = new
                s.save(update_fields=["claimable_amount"])
                updated += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Total students: {total} | Recalculated: {updated}"
            )
        )

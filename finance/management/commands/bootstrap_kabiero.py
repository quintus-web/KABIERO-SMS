from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.core.exceptions import ImproperlyConfigured

from finance.models import ClassStream, FeeStructure
from finance.school_config import CBC_LEVELS, DEFAULT_FEE_AMOUNT


class Command(BaseCommand):
    help = "Creates Kabiero Academy's empty CBC structure and administrator without demo records."

    def handle(self, *args, **options):
        for level in CBC_LEVELS:
            ClassStream.objects.get_or_create(name=level)
            for term in ("TERM_1", "TERM_2", "TERM_3"):
                FeeStructure.objects.get_or_create(
                    level=level,
                    term=term,
                    year=2026,
                    defaults={"amount": Decimal(DEFAULT_FEE_AMOUNT)},
                )

        username = __import__('os').environ.get('DEFAULT_ADMIN_USERNAME')
        password = __import__('os').environ.get('DEFAULT_ADMIN_PASSWORD')
        if not username or not password:
            raise ImproperlyConfigured("DEFAULT_ADMIN_USERNAME and DEFAULT_ADMIN_PASSWORD must be set in the environment.")
        user, created = User.objects.get_or_create(username=username)
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.email = user.email or 'admin@admin.com'
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(
            f"Kabiero Academy is ready: {len(CBC_LEVELS)} CBC levels, blank fee schedules, admin '{username}'."
        ))

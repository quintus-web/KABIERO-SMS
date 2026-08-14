# finance/management/commands/import_xlsx.py
import os
import re
import random
import string
import datetime

import django
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sms_core.settings')
django.setup()

import openpyxl
from openpyxl import load_workbook

from finance.models import Student, ClassStream, StaffProfile, Subject, Teacher
from finance.school_config import CBC_LEVELS


EXCEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "PP1 Student list (6).xlsx")


def split_name(full_name):
    parts = full_name.strip().split()
    if not parts:
        return "", ""
    first = parts[0]
    last = " ".join(parts[1:]) if len(parts) > 1 else ""
    return first, last


def generate_password(length=10):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


class Command(BaseCommand):
    help = "Imports students and staff from the Kabiero Academy Excel workbook into the Django database."

    def handle(self, *args, **options):
        if not os.path.exists(EXCEL_PATH):
            self.stdout.write(self.style.ERROR(f"Excel file not found at: {EXCEL_PATH}"))
            return

        wb = load_workbook(EXCEL_PATH, data_only=True)

        with transaction.atomic():
            self.import_students(wb)
            self.import_staff(wb)

        self.stdout.write(self.style.SUCCESS("Import completed successfully."))

    def import_students(self, wb):
        if "Data Entry" not in wb.sheetnames:
            self.stdout.write(self.style.WARNING("Sheet 'Data Entry' not found."))
            return

        ws = wb["Data Entry"]
        student_count = 0
        stream_count = 0

        for row in ws.iter_rows(min_row=6, values_only=True):
            adm_no = row[1]
            name = row[2]
            grade = row[3]
            balance_raw = row[4]
            parent_name = row[5]
            parent_phone = row[6]

            if adm_no is None or name is None or grade is None:
                continue

            if isinstance(adm_no, float):
                adm_no = str(int(adm_no))
            else:
                adm_no = str(adm_no).strip()
            name = str(name).strip()
            grade = str(grade).strip()
            balance_raw = balance_raw if balance_raw is not None else 0
            parent_name = str(parent_name).strip() if parent_name is not None else ""
            parent_phone = str(parent_phone).strip() if parent_phone is not None else ""

            if not adm_no or not name or not grade:
                continue

            grade = grade.strip()
            if grade not in CBC_LEVELS:
                self.stdout.write(self.style.WARNING(f"Skipping unknown grade '{grade}' for adm {adm_no}"))
                continue

            stream_instance, created = ClassStream.objects.get_or_create(name=grade)
            if created:
                stream_count += 1

            first_name, last_name = split_name(name)

            try:
                balance = float(balance_raw) if balance_raw is not None else 0.0
            except (TypeError, ValueError):
                balance = 0.0

            student, created = Student.objects.update_or_create(
                admission_number=adm_no,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "class_stream": stream_instance,
                    "guardian_name": parent_name or "Not Provided",
                    "parent_phone": parent_phone or "0700000000",
                    "current_balance": balance,
                    "status": "ACTIVE",
                    "is_active": True,
                },
            )
            if created:
                student_count += 1

        self.stdout.write(self.style.SUCCESS(f"Students: {student_count} created, streams: {stream_count} created."))

    def import_staff(self, wb):
        if "Staff Directory" not in wb.sheetnames:
            self.stdout.write(self.style.WARNING("Sheet 'Staff Directory' not found."))
            return

        ws = wb["Staff Directory"]
        staff_count = 0

        for row in ws.iter_rows(min_row=6, values_only=True):
            no_col = row[1]
            staff_id = row[2]
            full_name = row[3]
            gender = row[4]
            phone = row[5]
            position = row[6]
            subject_dept = row[7]
            employment_type = row[8]
            date_joined = row[9]
            status_raw = row[10]

            if not full_name:
                continue

            full_name = str(full_name).strip()
            if not full_name:
                continue

            if isinstance(staff_id, float):
                staff_id = str(int(staff_id))
            else:
                staff_id = str(staff_id).strip() if staff_id is not None else ""
            if staff_id in ["—", "-", "None", ""]:
                staff_id = ""

            phone = str(phone).strip() if phone is not None else ""
            if phone in ["—", "-", "None", ""]:
                phone = ""

            position = str(position).strip() if position is not None else ""
            subject_dept = str(subject_dept).strip() if subject_dept is not None else ""
            status_raw = str(status_raw).strip() if status_raw is not None else ""

            first_name, last_name = split_name(full_name)
            if not last_name:
                last_name = "Staff"

            employee_number = staff_id if staff_id else f"EMP/{random.randint(1000, 9999)}"
            phone_line = phone if phone else "0700000000"

            role_map = {
                "Administrator": "PRINCIPAL",
                "Teacher": "TEACHER",
                "Support Staff": "SUPPORT",
            }
            role_designation = role_map.get(position, "SUPPORT")

            current_status = "ACTIVE"
            if status_raw:
                if status_raw.lower() in ["on leave", "suspended"]:
                    current_status = status_raw.upper().replace(" ", "_")

            username_base = re.sub(r"[^a-z0-9]", "", full_name.lower()[:20])
            username = username_base if username_base else f"staff{random.randint(1000, 9999)}"
            password = generate_password()

            user, user_created = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": "",
                },
            )
            if user_created:
                user.set_password(password)
                user.save()
                self.stdout.write(self.style.NOTICE(f"Created user {username} with password {password}"))

            specialization = subject_dept if subject_dept and subject_dept != "—" else "General"

            profile, created = StaffProfile.objects.update_or_create(
                user=user,
                defaults={
                    "employee_number": employee_number,
                    "role_designation": role_designation,
                    "phone_line": phone_line,
                    "specialization": specialization,
                    "base_salary_kes": 45000.00,
                    "current_status": current_status,
                    "performance_score": 85,
                },
            )
            if created:
                staff_count += 1

        self.stdout.write(self.style.SUCCESS(f"Staff: {staff_count} profiles created."))

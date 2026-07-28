# finance/management/commands/seed_data.py
import os
import csv
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from finance.models import Student, ClassStream, Subject, FeeStructure, FeeInvoice, StaffProfile

VALID_GRADES = ["Day care", "Play Group", "PP1", "PP2", "Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5", "Grade 6"]


def normalize_grade(raw_grade):
    grade = (raw_grade or "").strip()
    return grade if grade in VALID_GRADES else "Grade 1"

class Command(BaseCommand):
    help = "Parses the master school CSV dataset and seeds the SQLite database tables seamlessly."

    def handle(self, *args, **options):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        csv_path = os.path.join(base_dir, "Kabiero School - STUDENTS.csv")
        fees_path = os.path.join(base_dir, "Kabiero_Fees_2026.csv")

        term_fee_map = {}
        if os.path.exists(fees_path):
            with open(fees_path, newline="", encoding="utf-8") as fee_file:
                fee_reader = csv.reader(fee_file)
                next(fee_reader, None)
                for row in fee_reader:
                    if not row or len(row) < 4:
                        continue
                    level = row[0].strip()
                    term_1 = Decimal(row[1].strip())
                    term_2 = Decimal(row[2].strip())
                    term_3 = Decimal(row[3].strip())
                    term_fee_map[level] = {'TERM_1': term_1, 'TERM_2': term_2, 'TERM_3': term_3}

                    FeeStructure.objects.get_or_create(
                        level=level,
                        term='TERM_1',
                        year=2026,
                        defaults={'amount': term_1}
                    )
                    FeeStructure.objects.get_or_create(
                        level=level,
                        term='TERM_2',
                        year=2026,
                        defaults={'amount': term_2}
                    )
                    FeeStructure.objects.get_or_create(
                        level=level,
                        term='TERM_3',
                        year=2026,
                        defaults={'amount': term_3}
                    )

            self.stdout.write(self.style.SUCCESS(f"Seeded {len(term_fee_map)} fee structures for 2026."))

        if os.path.exists(csv_path):
            self.stdout.write(self.style.WARNING("Starting Milestone 1: Data Engine Migration parsing pipeline..."))
            with open(csv_path, newline="", encoding="utf-8") as file:
                reader = csv.reader(file)
                header = next(reader, None)

                student_count = 0
                stream_count = 0
                invoice_count = 0

                core_subjects = [
                    ("Mathematics", "MAT101"),
                    ("English", "ENG101"),
                    ("Kiswahili", "KIS101"),
                    ("Science", "SCI101"),
                    ("Social Studies", "SST101"),
                    ("CRE", "CRE101"),
                    ("Art & Craft", "ART101"),
                    ("Music", "MUS101"),
                    ("Physical Education", "PE101"),
                    ("Agriculture", "AGR101"),
                ]
                for name, code in core_subjects:
                    Subject.objects.get_or_create(code=code, defaults={"name": name})

                for row in reader:
                    if not row or len(row) < 6:
                        continue

                    adm_no = row[0].strip()
                    full_name = row[1].strip()
                    gender_raw = row[2].strip().upper()
                    stream_name = normalize_grade(row[5])
                    guardian = row[8].strip() if len(row) > 8 else "Not Provided"
                    phone = row[9].strip() if len(row) > 9 else "0700000000"

                    name_parts = full_name.split(" ", 1)
                    first_name = name_parts[0]
                    last_name = name_parts[1] if len(name_parts) > 1 else "Ondicho"

                    gender = 'F' if gender_raw in ['F', 'FEMALE', 'GIRL'] else 'M'

                    stream_instance, created = ClassStream.objects.get_or_create(name=stream_name)
                    if created:
                        stream_count += 1

                    term_fees = term_fee_map.get(stream_name, {'TERM_1': Decimal("0.00")})
                    opening_balance = term_fees.get('TERM_1', Decimal("0.00"))

                    student, created = Student.objects.update_or_create(
                        admission_number=adm_no,
                        defaults={
                            'first_name': first_name,
                            'last_name': last_name,
                            'gender': gender,
                            'class_stream': stream_instance,
                            'guardian_name': guardian,
                            'parent_phone': phone,
                        }
                    )
                    # Only set opening balance on first creation — never overwrite manually entered balances
                    if created:
                        student.current_balance = opening_balance
                        student.save(update_fields=['current_balance'])
                    if created:
                        student_count += 1

                    if created and opening_balance > 0:
                        FeeInvoice.objects.get_or_create(
                            student=student,
                            title=f"{stream_name} Term 1 Fees 2026",
                            defaults={
                                'amount': opening_balance,
                                'description': f"Auto-generated from Kabiero Fee Structure 2026 for {stream_name}"
                            }
                        )
                        invoice_count += 1

            self.stdout.write(self.style.SUCCESS(
                f"Milestone 1 Complete! {stream_count} streams, {student_count} students, {invoice_count} invoices."
            ))
        else:
            self.stdout.write(self.style.WARNING("Data file not found, skipping student seed"))

        admin_username = os.environ.get('DEFAULT_ADMIN_USERNAME', 'admin')
        admin_password = os.environ.get('DEFAULT_ADMIN_PASSWORD', 'sms_pass2026')
        user, _ = User.objects.get_or_create(
            username=admin_username,
            defaults={
                'email': 'admin@admin.com'
            }
        )
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.email = user.email or 'admin@admin.com'
        user.set_password(admin_password)
        user.save()
        self.stdout.write(self.style.SUCCESS(f"Admin user ready (username: {admin_username})"))

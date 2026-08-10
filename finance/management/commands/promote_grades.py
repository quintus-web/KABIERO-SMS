# finance/management/commands/promote_grades.py
from django.core.management.base import BaseCommand
from finance.models import Student, ClassStream, FeeInvoice
from django.utils import timezone

from finance.school_config import CBC_LEVELS

VALID_GRADES = CBC_LEVELS


def get_next_grade(current_grade_name):
    if not current_grade_name:
        return None
    try:
        idx = VALID_GRADES.index(current_grade_name)
        if idx < len(VALID_GRADES) - 1:
            return VALID_GRADES[idx + 1]
    except ValueError:
        pass
    return None


class Command(BaseCommand):
    help = "Promotes all active students to the next grade level. Grade 9 students are marked as graduated."

    def handle(self, *args, **options):
        active_students = Student.objects.filter(status='ACTIVE', is_active=True).exclude(class_stream__isnull=True)
        promoted_count = 0
        graduated_count = 0
        skipped_count = 0

        for student in active_students:
            current_grade = student.class_stream.name
            next_grade = get_next_grade(current_grade)

            if next_grade is None:
                skipped_count += 1
                continue

            if current_grade == "Grade 9":
                student.status = 'GRADUATED'
                student.is_active = False
                student.class_stream = None
                graduated_count += 1
            else:
                new_stream, _ = ClassStream.objects.get_or_create(name=next_grade)
                student.class_stream = new_stream
                promoted_count += 1

            student.save()

        self.stdout.write(self.style.SUCCESS(
            f"Promotion complete: {promoted_count} promoted, {graduated_count} graduated, {skipped_count} skipped."
        ))

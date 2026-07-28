# prep_demo_data.py
import os
import django
from decimal import Decimal

# Initialize the Django environment context configuration
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management_system.settings')
try:
    django.setup()
except ModuleNotFoundError:
    # Fallback in case your core folder name matches the interior app settings directory
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sms_core.settings')
    django.setup()

from finance.models import Teacher, ClassStream, Subject, Student, FeeInvoice, ExamRecord, FeeReceipt

def stage_demo_environment():
    print("✨ Purging old entries and staging comprehensive database framework for Kabiero...")
    
    # 1. Clear existing records in strict dependency order to prevent foreign key errors
    ExamRecord.objects.all().delete()
    FeeReceipt.objects.all().delete()
    FeeInvoice.objects.all().delete()
    Student.objects.all().delete()
    Subject.objects.all().delete()
    ClassStream.objects.all().delete()
    Teacher.objects.all().delete()

    print("👥 Seeding professional Kabiero faculty profiles...")
    # 2. Seed Teacher Profiles
    teacher_one = Teacher.objects.create(
        tsc_number="TSC-889922",
        first_name="Ezekiel",
        last_name="Mutua",
    email="ezekiel.mutua@kabiero.ac.ke",
        phone_number="+254711002233",
        is_class_teacher=True
    )
    
    teacher_two = Teacher.objects.create(
        tsc_number="TSC-114455",
        first_name="Sarah",
        last_name="Omwamba",
    email="sarah.omwamba@kabiero.ac.ke",
        phone_number="+254722998877",
        is_class_teacher=True
    )

    print("🏫 Establishing class streams with master class teachers assigned...")
    # 3. Create Class Streams linked to master teachers
    form_one_east = ClassStream.objects.create(name="Form 1 East", class_teacher=teacher_one)
    form_two_west = ClassStream.objects.create(name="Form 2 West", class_teacher=teacher_two)
    
    print("📚 Registering core academic subjects and assigning specialized teachers...")
    # 4. Create Subjects and map teachers using many-to-many relationship
    math = Subject.objects.create(code="MAT", name="Mathematics")
    math.teachers.add(teacher_one)
    
    english = Subject.objects.create(code="ENG", name="English")
    english.teachers.add(teacher_two)
    
    kiswahili = Subject.objects.create(code="KIS", name="Kiswahili")
    kiswahili.teachers.add(teacher_one)

    print("🧑‍🎓 Registering student files into active stream groups...")
    # 5. Create Demo Students
    # Structure: (Admission Number, First Name, Last Name, Class Stream Object, Parent Phone, Term 1 Base Invoice Amount)
    students_to_create = [
        ('101', 'John', 'Kamau', form_one_east, '+254712345678', 35000.00),
        ('102', 'Amina', 'Mohamed', form_one_east, '+254722112233', 35000.00),
        ('103', 'Grace', 'Omwamba', form_one_east, '+254733445566', 35000.00),
        ('201', 'David', 'Ochieng', form_two_west, '+254744556677', 38000.00),
    ]

    student_records = {}
    for adm, first, last, stream, phone, base_fee in students_to_create:
        student = Student.objects.create(
            admission_number=adm,
            first_name=first,
            last_name=last,
            class_stream=stream,
            parent_phone=phone,
            is_active=True
        )
        student_records[adm] = student
        
        # Issue an initial Term 1 invoice instantly for each profile
        FeeInvoice.objects.create(
            student=student,
            term='TERM_1',
            year=2026,
            amount=Decimal(base_fee)
        )

    print("💰 Processing simulated fee collection bank transactions...")
    # 6. Post real-time M-Pesa receipts to show cleared/partial accounts
    # Amina Mohamed - Completely Cleared
    FeeReceipt.objects.create(
        student=student_records['102'],
        reference_code="MPESA_AMNA99",
        amount_paid=Decimal(35000.00),
        payment_channel="MPESA",
        status="COMPLETED"
    )
    
    # Grace Omwamba - Partially Paid (Leaves a balance of KES 15,000 for SMS module testing)
    FeeReceipt.objects.create(
        student=student_records['103'],
        reference_code="MPESA_GRCE44",
        amount_paid=Decimal(20000.00),
        payment_channel="MPESA",
        status="COMPLETED"
    )

    print("📝 Logging analytical exam tracking metrics across consecutive terms...")
    # 7. Seed Exam Records for Form 1 East Mathematics to trigger the trajectory variances
    
    # John Kamau: Grades are slipping significantly
    ExamRecord.objects.create(student=student_records['101'], subject=math, term='TERM_1', year=2026, cat_1=12.0, cat_2=13.0, final_exam=60.0)  # Total: 85.0%
    ExamRecord.objects.create(student=student_records['101'], subject=math, term='TERM_2', year=2026, cat_1=8.0, cat_2=9.0, final_exam=45.0)    # Total: 62.0% (Variance: -23.0%)

    # Amina Mohamed: Grades are climbing sharply
    ExamRecord.objects.create(student=student_records['102'], subject=math, term='TERM_1', year=2026, cat_1=9.0, cat_2=8.0, final_exam=48.0)    # Total: 65.0%
    ExamRecord.objects.create(student=student_records['102'], subject=math, term='TERM_2', year=2026, cat_1=14.0, cat_2=13.0, final_exam=62.0)  # Total: 89.0% (Variance: +24.0%)

    # Grace Omwamba: Grades are completely stable
    ExamRecord.objects.create(student=student_records['103'], subject=math, term='TERM_1', year=2026, cat_1=10.0, cat_2=11.0, final_exam=53.0)  # Total: 74.0%
    ExamRecord.objects.create(student=student_records['103'], subject=math, term='TERM_2', year=2026, cat_1=11.0, cat_2=10.0, final_exam=54.0)  # Total: 75.0% (Variance: +1.0%)

    print("\n==================================================================")
    print("✅ Kabiero DEMO SYSTEM INSTANTLY LOADED WITH MASTER DATA!")
    print(f"   🔹 Registered Teachers: {Teacher.objects.count()}")
    print(f"   🔹 Formatted Streams:  {ClassStream.objects.count()}")
    print(f"   🔹 Active Students:    {Student.objects.count()}")
    print(f"   🔹 Tracked Exam lines: {ExamRecord.objects.count()}")
    print("==================================================================")

if __name__ == '__main__':
    stage_demo_environment()

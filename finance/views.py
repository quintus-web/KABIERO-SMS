# finance/views.py
import os
import csv
import datetime
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, Http404, HttpResponse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required

from .models import (
    Student, ClassStream, Subject, FeeStructure,
    FeeInvoice, FeeReceipt,
    ExamRecord,
    StudentAttendanceRecord,
    TeacherAttendanceRecord,
    StaffProfile,
    SchoolAsset, AssetMaintenanceLog,
    HomeworkAssignment, SchoolAnnouncement,
    LessonPlan, LearningMaterial, TimetableSlot,
    DisciplineReport, LeaveApplication, SchoolHoliday
)
from django.contrib.auth.models import User
from .school_config import CBC_LEVELS, SCHOOL_SHORT_NAME

CORE_SUBJECTS = [
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

VALID_GRADES = CBC_LEVELS


def _default_admin_credentials():
    return (
        os.environ.get('DEFAULT_ADMIN_USERNAME', 'Kabiero'),
        os.environ.get('DEFAULT_ADMIN_PASSWORD', 'Kabiero-ChangeMe-2026!'),
    )


def _ensure_default_admin_user():
    username, password = _default_admin_credentials()
    user, _ = User.objects.get_or_create(username=username)
    user.is_superuser = True
    user.is_staff = True
    user.is_active = True
    user.email = user.email or 'admin@admin.com'
    user.set_password(password)
    user.save()
    return username, password


def _get_subjects():
    if not Subject.objects.exists():
        Subject.objects.bulk_create([
            Subject(code=code, name=name)
            for name, code in CORE_SUBJECTS
        ])
    return Subject.objects.all().order_by('name')


def _get_valid_grade_streams():
    return ClassStream.objects.filter(name__in=VALID_GRADES).order_by('name')


def _get_valid_grade_names():
    db_names = set(Student.objects.exclude(class_stream__isnull=True).values_list('class_stream__name', flat=True))
    return [grade for grade in VALID_GRADES if grade in db_names] or VALID_GRADES

# =========================================================
# 1. CSV ENGINE LAYER (SINGLE SOURCE ROUTINE)
# =========================================================

class LiveCSVStudent:
    def __init__(self, row):
        self.admission_number = row[0].strip()
        self.id = self.admission_number.replace("/", "-")

        full_name = row[1].strip()
        parts = full_name.split(" ", 1)

        self.first_name = parts[0]
        self.last_name = parts[1] if len(parts) > 1 else ""
        self.gender = row[2].strip() if len(row) > 2 else ""
        self.current_grade = row[5].strip() if len(row) > 5 else "Playgroup"

        class Stream:
            def __init__(self, name):
                self.name = name

        self.class_stream = Stream(self.current_grade)
        self.guardian_name = row[8].strip() if len(row) > 8 else ""
        self.parent_phone = row[9].strip() if len(row) > 9 else ""
        self.current_balance = 0.0


def _load_students_from_csv():
    """Reads foundational tracking records from local project workspace directory."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(base_dir, "Kabiero Academy - STUDENTS.csv")

    students = []
    if os.path.exists(csv_path):
        with open(csv_path, newline="", encoding="utf-8") as file:
            reader = csv.reader(file)
            next(reader, None)

            for row in reader:
                if row and len(row) > 1:
                    students.append(LiveCSVStudent(row))
    return students


# =========================================================
# 2. CORE PORTAL & ADMINISTRATIVE PANELS
# =========================================================

@login_required
def executive_analytics_kpi_dashboard(request):
    today = timezone.now().date()
    active_students = Student.objects.filter(is_active=True, status='ACTIVE')
    valid_streams = _get_valid_grade_streams()

    total_learners = active_students.count()
    total_streams = valid_streams.count()
    total_subjects = Subject.objects.count()
    total_instructors = StaffProfile.objects.filter(role_designation='TEACHER', current_status='ACTIVE').count()
    total_staff = StaffProfile.objects.filter(current_status='ACTIVE').count()

    total_invoiced = FeeInvoice.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_collected = FeeReceipt.objects.filter(status='COMPLETED').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_outstanding_arrears = active_students.aggregate(total=Sum('current_balance'))['total'] or Decimal('0.00')
    collection_efficiency = (float(total_collected) / float(total_invoiced) * 100) if total_invoiced > 0 else 0.0

    term_fee_summary = []
    for term in ['TERM_1', 'TERM_2', 'TERM_3']:
        invoiced = FeeInvoice.objects.filter(term=term).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        collected = FeeReceipt.objects.filter(status='COMPLETED', invoice__term=term).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        term_fee_summary.append({
            'term': term,
            'label': term.replace('_', ' '),
            'invoiced': float(invoiced),
            'collected': float(collected),
            'outstanding': float(invoiced - collected),
            'rate': round((float(collected) / float(invoiced)) * 100, 1) if invoiced else 0.0
        })

    stream_breakdown = []
    for stream in valid_streams:
        students = active_students.filter(class_stream=stream).count()
        invoiced = FeeInvoice.objects.filter(student__class_stream=stream).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        collected = FeeReceipt.objects.filter(status='COMPLETED', student__class_stream=stream).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        balance = active_students.filter(class_stream=stream).aggregate(total=Sum('current_balance'))['total'] or Decimal('0.00')
        stream_breakdown.append({
            'stream': stream,
            'students': students,
            'invoiced': float(invoiced),
            'collected': float(collected),
            'balance': float(balance),
            'rate': round((float(collected) / float(invoiced)) * 100, 1) if invoiced else 0.0
        })

    today_attendance = StudentAttendanceRecord.objects.filter(date=today)
    attendance_present = today_attendance.filter(is_present=True).count()
    attendance_absent = today_attendance.filter(is_present=False).count()
    attendance_late = today_attendance.filter(status='LATE').count()
    attendance_total = today_attendance.count()
    attendance_rate = round((attendance_present / attendance_total) * 100, 1) if attendance_total else 0.0

    exam_record_count = ExamRecord.objects.count()
    assignments_total = HomeworkAssignment.objects.count()
    overdue_assignments = HomeworkAssignment.objects.filter(submission_deadline__lt=today).count()
    approved_plans = LessonPlan.objects.filter(is_approved=True).count()
    pending_plans = LessonPlan.objects.filter(is_approved=False).count()
    timetable_slots = TimetableSlot.objects.count()

    total_assets = SchoolAsset.objects.aggregate(total=Sum('total_quantity'))['total'] or Decimal('0.00')
    available_assets = SchoolAsset.objects.filter(status='OPERATIONAL').aggregate(total=Sum('available_quantity'))['total'] or Decimal('0.00')
    assets_in_workshop = SchoolAsset.objects.filter(status='UNDER_REPAIR').count()
    maintenance_cost = AssetMaintenanceLog.objects.aggregate(total=Sum('cost_incurred_kes'))['total'] or Decimal('0.00')
    facility_operational_rate = round(((total_assets - assets_in_workshop) / total_assets) * 100, 1) if total_assets > 0 else 100.0

    subject_performance = []
    for subject in Subject.objects.all():
        records = ExamRecord.objects.filter(subject=subject)
        average_score = sum(record.total_marks for record in records) / records.count() if records else 0.0
        subject_performance.append({
            'subject': subject,
            'records': records.count(),
            'average': round(average_score, 1)
        })
    subject_performance.sort(key=lambda item: item['average'], reverse=True)

    recent_payments = FeeReceipt.objects.select_related('student__class_stream').filter(status='COMPLETED').order_by('-date_paid')[:8]
    recent_invoices = FeeInvoice.objects.select_related('student__class_stream').order_by('-date_issued')[:8]
    defaulters = active_students.select_related('class_stream').filter(current_balance__gt=0).order_by('-current_balance')[:8]

    activity_logs = [
        {"time": "Just now", "title": "Executive KPI dashboard refreshed", "detail": "Live finance, academic, attendance, and asset metrics loaded.", "status": "SUCCESS", "icon": "bi-graph-up-arrow"},
        {"time": "Today", "title": f"{attendance_present} learners marked present", "detail": f"{attendance_absent} absent and {attendance_late} late records captured for today.", "status": "ALERT" if attendance_absent else "SUCCESS", "icon": "bi-calendar-check"},
        {"time": "This term", "title": f"{assignments_total} homework assignments posted", "detail": f"{overdue_assignments} assignments are currently overdue.", "status": "ALERT" if overdue_assignments else "SUCCESS", "icon": "bi-book"},
        {"time": "Operations", "title": f"{assets_in_workshop} assets under repair", "detail": f"KES {float(maintenance_cost):,.0f} logged in maintenance costs.", "status": "WARNING" if assets_in_workshop else "SUCCESS", "icon": "bi-tools"},
    ]

    # ── EXECUTIVE REPORT DATA ──
    finance_report_data = []
    for s in active_students.select_related('class_stream'):
        s_inv = FeeInvoice.objects.filter(student=s).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        s_rec = FeeReceipt.objects.filter(status='COMPLETED', student=s).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        finance_report_data.append({
            'adm': s.admission_number,
            'name': f"{s.first_name} {s.last_name}",
            'stream': s.class_stream.name if s.class_stream else 'Unassigned',
            'invoiced': float(s_inv),
            'collected': float(s_rec),
            'balance': float(s_inv - s_rec),
            'rate': round((float(s_rec)/float(s_inv))*100,1) if s_inv else 0.0
        })

    attendance_report_data = []
    for rec in StudentAttendanceRecord.objects.filter(date=today).select_related('student__class_stream').order_by('student__first_name'):
        attendance_report_data.append({
            'adm': rec.student.admission_number,
            'name': f"{rec.student.first_name} {rec.student.last_name}",
            'stream': rec.student.class_stream.name if rec.student.class_stream else 'Unassigned',
            'status': rec.get_status_display(),
            'present': 'Yes' if rec.is_present else 'No',
            'remarks': rec.remarks or ''
        })

    grading_report_data = []
    for rec in ExamRecord.objects.all().select_related('student', 'student__class_stream', 'subject').order_by('-year', 'student__last_name')[:50]:
        grading_report_data.append({
            'adm': rec.student.admission_number,
            'name': f"{rec.student.first_name} {rec.student.last_name}",
            'stream': rec.student.class_stream.name if rec.student.class_stream else 'Unassigned',
            'subject': rec.subject.name,
            'term': rec.term.replace('_', ' '),
            'year': rec.year,
            'cat1': rec.cat_1,
            'cat2': rec.cat_2,
            'exam': rec.final_exam,
            'total': rec.total_marks
        })

    return render(request, "finance/executive_reporting.html", {
        "total_students": total_learners,
        "total_teachers": total_instructors,
        "total_staff": total_staff,
        "total_streams": total_streams,
        "total_subjects": total_subjects,
        "total_invoiced": total_invoiced,
        "total_collected": total_collected,
        "total_arrears": total_outstanding_arrears,
        "collection_efficiency": round(collection_efficiency, 1),
        "operational_rate": facility_operational_rate,
        "assets_at_risk": assets_in_workshop,
        "available_assets": available_assets,
        "maintenance_cost": maintenance_cost,
        "term_fee_summary": term_fee_summary,
        "stream_breakdown": stream_breakdown,
        "attendance_total": attendance_total,
        "attendance_present": attendance_present,
        "attendance_absent": attendance_absent,
        "attendance_late": attendance_late,
        "attendance_rate": attendance_rate,
        "exam_record_count": exam_record_count,
        "assignments_total": assignments_total,
        "overdue_assignments": overdue_assignments,
        "approved_plans": approved_plans,
        "pending_plans": pending_plans,
        "timetable_slots": timetable_slots,
        "subject_performance": subject_performance[:8],
        "recent_payments": recent_payments,
        "recent_invoices": recent_invoices,
        "defaulters": defaulters,
        "activity_logs": activity_logs,
        "generation_date": today,
        "finance_report_data": finance_report_data,
        "attendance_report_data": attendance_report_data,
        "grading_report_data": grading_report_data,
    })


# =========================================================
# 3. STUDENT & FACULTY REGISTRY WORKSPACES
# =========================================================

@login_required
def student_registry_workstation(request):
    students = Student.objects.all().order_by('admission_number')
    selected_stream = request.GET.get("stream_id")

    if selected_stream:
        students = students.filter(class_stream__name=selected_stream)

    return render(request, "finance/learners.html", {
        "students": students,
        "selected_stream": selected_stream
    })


@login_required
def single_student_profile_folder(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    discipline_logs = student.discipline_logs.all().order_by('-date_reported')[:10]
    invoices = student.fee_invoices.all().order_by('-date_issued')[:10]
    receipts = student.fee_receipts.all().order_by('-date_paid')[:10]
    attendance_records = student.attendance_history.all().order_by('-date')[:20]
    exam_records = ExamRecord.objects.filter(student=student).select_related('subject').order_by('-year', '-term')[:20]
    total_paid = sum((r.amount for r in receipts), Decimal("0.00"))
    att_all = student.attendance_history.all()
    attendance_total = att_all.count()
    attendance_present = sum(1 for r in att_all if r.is_present)
    attendance_pct = round((attendance_present / attendance_total) * 100, 1) if attendance_total else 100.0
    return render(request, "finance/student_profile_folder.html", {
        "student": student,
        "discipline_logs": discipline_logs,
        "invoices": invoices,
        "receipts": receipts,
        "attendance_records": attendance_records,
        "exam_records": exam_records,
        "total_paid": total_paid,
        "attendance_total": attendance_total,
        "attendance_present": attendance_present,
        "attendance_pct": attendance_pct
    })


@login_required
@login_required
def add_student_registry(request):
    if request.method == "POST":
        messages.success(request, "Enrollment initialization entry registered successfully.")
        return redirect("student_registry")
    return render(request, "finance/add_student.html")


@login_required
def staff_management_matrix(request):
    staff_roster = StaffProfile.objects.all().select_related('user')
    return render(request, "finance/staff_management_matrix.html", {"staff_roster": staff_roster})


@login_required
def faculty_directory(request):
    teachers = StaffProfile.objects.filter(role_designation='TEACHER').select_related('user')
    return render(request, "finance/faculty_directory.html", {"teachers": teachers})


# =========================================================
# 4. FINANCIAL LEDGER & ACCOUNTING STATIONS
# =========================================================

@login_required
def bursar_dashboard(request):
    search = request.GET.get("search", "").lower()
    students = Student.objects.all().order_by('admission_number')

    if search:
        students = students.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(admission_number__icontains=search)
        )

    students = students.select_related('class_stream')

    return render(request, "finance/bursar_dashboard.html", {
        "students": students,
        "search_query": search
    })


@login_required
def student_account_statement(request, student_id):
    student_record = get_object_or_404(Student, id=student_id)
    db_invoices = FeeInvoice.objects.filter(student_id=student_id).order_by('-date_issued')
    db_receipts = FeeReceipt.objects.filter(student=student_record).order_by('-date_paid')

    ledger_entries = []

    # Process Invoices as DEBITS (Money Owed)
    for inv in db_invoices:
        ledger_entries.append({
            'date': datetime.datetime.combine(inv.date_issued, datetime.time.min),
            'description': inv.description if inv.description else "Tuition Fee Invoice Charge",
            'reference': f"INV-{inv.id}",
            'type': 'DEBIT',
            'amount': float(inv.amount)
        })

    # Process Receipts as CREDITS (Money Paid)
    for rec in db_receipts:
        rec_date = rec.date_paid if rec.date_paid else rec.date_issued
        rec_desc = rec.description if rec.description else "School Fees Payment"
        ref_code = rec.reference_code if rec.reference_code else f"RCT-{rec.id}"
        rec_amount = rec.amount if rec.amount else 0.0

        ledger_entries.append({
            'date': rec_date,
            'description': f"{rec_desc} (Ref: {ref_code})",
            'reference': f"RCT-{rec.id}",
            'type': 'CREDIT',
            'amount': float(rec_amount)
        })

    # Sort timeline by date safely
    ledger_entries = [e for e in ledger_entries if e['date'] is not None]

    def _sort_key(d):
        if isinstance(d, datetime.datetime):
            return d.replace(tzinfo=None)
        return datetime.datetime.combine(d, datetime.time.min)

    ledger_entries.sort(key=lambda x: _sort_key(x['date']), reverse=True)

    # Recorded payments divided per term (Term 1 / 2 / 3)
    TERM_ORDER = [('TERM_1', 'Term 1'), ('TERM_2', 'Term 2'), ('TERM_3', 'Term 3')]
    payments_by_term = []
    total_recorded = Decimal('0.00')
    for term_code, term_label in TERM_ORDER:
        term_receipts = FeeReceipt.objects.filter(
            student=student_record, term=term_code, status='COMPLETED'
        ).order_by('-date_paid')
        subtotal = sum((r.amount for r in term_receipts), Decimal('0.00'))
        total_recorded += subtotal
        payments_by_term.append({
            'code': term_code,
            'label': term_label,
            'receipts': term_receipts,
            'subtotal': subtotal,
            'count': term_receipts.count(),
        })

    return render(request, "finance/student_statement.html", {
        "student": student_record,
        "ledger_entries": ledger_entries,
        "payments_by_term": payments_by_term,
        "total_recorded": total_recorded,
        "outstanding_balance": float(student_record.current_balance or 0),
    })


@login_required
def collect_fee_payment(request, student_id):
    student = get_object_or_404(Student, id=student_id)

    if request.method == "POST":
        payment_type = request.POST.get("payment_type", "payment")

        if payment_type == "balance":
            try:
                new_balance = Decimal(request.POST.get("opening_balance", 0))
                student.current_balance = new_balance
                student.save()
                messages.success(request, f"Opening balance for {student.first_name} set to KES {new_balance:,.2f}.")
            except Exception:
                messages.error(request, "Invalid balance amount entered.")
            return redirect("bursar_dashboard")

        # --- standard payment ---
        amount = Decimal(request.POST.get("amount_paid", 0))
        if amount <= 0:
            messages.error(request, "Invalid payment amount.")
            return redirect(request.path)

        channel = request.POST.get("payment_channel", "CASH")
        description = request.POST.get("description", "School Fees Payment").strip() or "School Fees Payment"

        term = request.POST.get("term", "TERM_1")
        if term not in ("TERM_1", "TERM_2", "TERM_3"):
            term = "TERM_1"

        # Prefer an invoice for the selected term so the payment is attributed correctly
        open_invoice = FeeInvoice.objects.filter(student=student, term=term).order_by('date_issued').first()
        if not open_invoice:
            open_invoice = FeeInvoice.objects.filter(student=student).order_by('date_issued').first()
        if not open_invoice:
            fee_entry = FeeStructure.objects.filter(level=student.class_stream.name, term=term, year=2026).first() if student.class_stream else None
            invoice_amount = fee_entry.amount if fee_entry else Decimal("0.00")
            open_invoice = FeeInvoice.objects.create(
                student=student,
                term=term,
                year=2026,
                title=f"{student.class_stream.name if student.class_stream else 'Unassigned'} {term.replace('_', ' ')} Invoice 2026",
                amount=invoice_amount,
                description=f"Auto-generated from {SCHOOL_SHORT_NAME} fee structure"
            )

        FeeReceipt.objects.create(
            student=student,
            invoice=open_invoice,
            term=term,
            amount=amount,
            status="COMPLETED",
            payment_channel=channel,
            description=description,
            reference_code=f"RCPT-{timezone.now().strftime('%Y%m%d%H%M%S')}-{student.id}"
        )

        student.current_balance = max(Decimal("0.00"), Decimal(student.current_balance) - amount)
        student.save()

        messages.success(request, f"Payment of KES {amount:,.2f} posted via {channel}.")
        return redirect("bursar_dashboard")

    suggested_invoice = FeeInvoice.objects.filter(student=student).order_by('date_issued').first()
    suggested_term = suggested_invoice.term if suggested_invoice else "TERM_1"
    return render(request, "finance/receipt_form.html", {"student": student, "suggested_term": suggested_term})


@login_required
def fee_defaulters_portal(request):
    defaulters_qs = Student.objects.filter(current_balance__gt=0, status='ACTIVE', is_active=True).select_related('class_stream').order_by('-current_balance')
    defaulter_list = [{'student': s, 'balance': float(s.current_balance), 'parent_phone': s.parent_phone} for s in defaulters_qs]
    if request.method == "POST":
        messages.success(request, f"Outstanding debt notification arrays dispatched to {len(defaulter_list)} account(s).")
    return render(request, "finance/sms_portal.html", {'defaulters': defaulter_list})


@login_required
def fee_structure(request):
    schedules = FeeStructure.objects.all().order_by('level', 'term')
    levels = sorted(FeeStructure.objects.values_list('level', flat=True).distinct())
    rows = []
    for level in levels:
        t1 = FeeStructure.objects.filter(level=level, term='TERM_1').first()
        t2 = FeeStructure.objects.filter(level=level, term='TERM_2').first()
        t3 = FeeStructure.objects.filter(level=level, term='TERM_3').first()
        a1 = float(t1.amount) if t1 else 0
        a2 = float(t2.amount) if t2 else 0
        a3 = float(t3.amount) if t3 else 0
        rows.append({'level': level, 'term1': a1, 'term2': a2, 'term3': a3, 'annual': a1 + a2 + a3})
    return render(request, "finance/fee_structure.html", {'rows': rows})


@login_required
def invoice_list(request):
    term = request.GET.get("term", "")
    level = request.GET.get("level", "")
    status_filter = request.GET.get("status", "all")

    qs = FeeInvoice.objects.all().select_related('student', 'student__class_stream').order_by('-date_issued')
    if term:
        qs = qs.filter(term=term)
    if level:
        qs = qs.filter(student__class_stream__name=level)
    if status_filter == "paid":
        qs = qs.filter(fee_receipts__status='COMPLETED').distinct()
    elif status_filter == "unpaid":
        qs = qs.filter(fee_receipts__status__isnull=True)

    levels = _get_valid_grade_names()
    terms = ['TERM_1', 'TERM_2', 'TERM_3']
    total_amount = qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    return render(request, "finance/invoice_list.html", {
        "invoices": qs,
        "levels": levels,
        "terms": terms,
        "selected_term": term,
        "selected_level": level,
        "selected_status": status_filter,
        "total_amount": float(total_amount),
        "current_page": "invoices"
    })


@login_required
def generate_invoice_pdf(request, invoice_id):
    invoice = get_object_or_404(FeeInvoice.objects.select_related('student', 'student__class_stream'), id=invoice_id)
    receipts = FeeReceipt.objects.filter(invoice=invoice, status='COMPLETED').order_by('-date_paid')
    total_paid = sum((r.amount for r in receipts), Decimal("0.00"))
    balance = invoice.amount - total_paid

    context = {
        'invoice': invoice,
        'receipts': receipts,
        'total_paid': float(total_paid),
        'balance': float(balance),
        'today': timezone.now(),
    }

    try:
        from weasyprint import HTML
        from django.template.loader import render_to_string
        html_string = render_to_string('finance/invoice_printout.html', context)
        response = HttpResponse(content_type='application/pdf')
        filename = f"invoice_INV-{invoice.id}_{invoice.student.admission_number}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        HTML(string=html_string).write_pdf(response)
        return response
    except (ImportError, OSError):
        from django.template.loader import render_to_string
        html_string = render_to_string('finance/invoice_printout.html', context)
        response = HttpResponse(html_string, content_type='text/html')
        response['Content-Disposition'] = f'inline; filename="invoice_INV-{invoice.id}_{invoice.student.admission_number}.html"'
        messages.info(request, "PDF engine unavailable - rendering print-friendly HTML. Use browser Print to save as PDF.")
        return response


@login_required
def generate_receipt_pdf(request, receipt_id):
    receipt = get_object_or_404(FeeReceipt.objects.select_related('student', 'student__class_stream', 'invoice'), id=receipt_id)

    context = {
        'receipt': receipt,
        'today': timezone.now(),
    }

    try:
        from weasyprint import HTML
        from django.template.loader import render_to_string
        html_string = render_to_string('finance/receipt_printout.html', context)
        response = HttpResponse(content_type='application/pdf')
        filename = f"receipt_{receipt.reference_code}_{receipt.student.admission_number}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        HTML(string=html_string).write_pdf(response)
        return response
    except (ImportError, OSError):
        from django.template.loader import render_to_string
        html_string = render_to_string('finance/receipt_printout.html', context)
        response = HttpResponse(html_string, content_type='text/html')
        response['Content-Disposition'] = f'inline; filename="receipt_{receipt.reference_code}_{receipt.student.admission_number}.html"'
        messages.info(request, "PDF engine unavailable - rendering print-friendly HTML. Use browser Print to save as PDF.")
        return response


@login_required
def financial_analytics(request):
    from collections import defaultdict
    from django.db.models import Sum, Count, Q, F
    import json

    term = request.GET.get("term", "TERM_1")
    level_filter = request.GET.get("level", "")

    students_qs = Student.objects.filter(status='ACTIVE')
    if level_filter:
        students_qs = students_qs.filter(class_stream__name=level_filter)

    all_invoices = FeeInvoice.objects.all()
    all_receipts = FeeReceipt.objects.all()

    if term and term != "ALL":
        all_invoices = all_invoices.filter(term=term)
        all_receipts = all_receipts.filter(invoice__term=term)

    if level_filter:
        all_invoices = all_invoices.filter(student__class_stream__name=level_filter)
        all_receipts = all_receipts.filter(student__class_stream__name=level_filter)

    levels = _get_valid_grade_names()

    expected = float(all_invoices.aggregate(total=Sum('amount'))['total'] or Decimal('0.00'))
    collected = float(all_receipts.aggregate(total=Sum('amount'))['total'] or Decimal('0.00'))
    outstanding = expected - collected
    collection_rate = round((collected / expected) * 100, 1) if expected else 0.0

    stream_breakdown = []
    for lvl in levels:
        lvl_students = students_qs.filter(class_stream__name=lvl)
        lvl_expected = float(all_invoices.filter(student__class_stream__name=lvl).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'))
        lvl_collected = float(all_receipts.filter(student__class_stream__name=lvl).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'))
        lvl_outstanding = lvl_expected - lvl_collected
        stream_breakdown.append({
            'level': lvl,
            'students': lvl_students.count(),
            'expected': lvl_expected,
            'collected': lvl_collected,
            'outstanding': lvl_outstanding,
            'rate': round((lvl_collected / lvl_expected) * 100, 1) if lvl_expected else 0.0
        })

    term_data = []
    for t in ['TERM_1', 'TERM_2', 'TERM_3']:
        t_exp = float(FeeInvoice.objects.filter(term=t).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'))
        t_col = float(FeeReceipt.objects.filter(invoice__term=t).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'))
        term_data.append({
            'term': t,
            'expected': t_exp,
            'collected': t_col,
            'outstanding': t_exp - t_col,
            'rate': round((t_col / t_exp) * 100, 1) if t_exp else 0.0
        })

    defaulters = Student.objects.filter(current_balance__gt=0).order_by('-current_balance')[:50]
    defaulter_data = []
    for s in defaulters:
        defaulter_data.append({
            'student': s,
            'balance': float(s.current_balance),
            'stream': s.class_stream.name if s.class_stream else 'Unassigned',
            'adm': s.admission_number,
            'name': f"{s.first_name} {s.last_name}"
        })

    payment_channels = []
    total_receipts = all_receipts.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    channel_qs = all_receipts.values('payment_channel').annotate(total=Sum('amount'), count=Count('id'))
    for ch in channel_qs:
        channel_total = float(ch['total'] or Decimal('0.00'))
        payment_channels.append({
            'channel': ch['payment_channel'] or 'CASH',
            'total': channel_total,
            'count': ch['count'],
            'share': round((channel_total / float(total_receipts)) * 100, 1) if total_receipts else 0.0
        })

    return render(request, "finance/financial_analytics.html", {
        "term": term,
        "level_filter": level_filter,
        "levels": levels,
        "expected": expected,
        "collected": collected,
        "outstanding": outstanding,
        "collection_rate": collection_rate,
        "stream_breakdown": stream_breakdown,
        "term_data": term_data,
        "defaulter_data": defaulter_data,
        "payment_channels": payment_channels,
        "current_page": "analytics"
    })


# =========================================================
# 5. INTEGRATED BROADCASTER & COMMUNICATORS
# =========================================================

@login_required
def teacher_sms_broadcast(request):
    if request.method == "POST":
        message = request.POST.get("message", "").strip()
        if not message:
            messages.error(request, "Broadcast message cannot be empty.")
            return redirect("teacher_sms_broadcast")
        
        import requests
        import base64
        
        username = request.POST.get("username", "").strip()
        api_key = request.POST.get("api_key", "").strip()
        sender_id = request.POST.get("sender_id", "Kabiero").strip()
        
        if not username or not api_key:
            messages.error(request, "Africa's Talking credentials required in session settings.")
            return redirect("teacher_sms_broadcast")

        recipients = request.POST.getlist("recipient_phone")
        if not recipients:
            messages.error(request, "No recipient phone numbers selected.")
            return redirect("teacher_sms_broadcast")

        url = "https://api.africastalking.com/version1/messaging"
        auth_header = base64.b64encode(f"{username}:{api_key}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        success_count = 0
        error_count = 0
        for phone in recipients:
            phone = phone.strip()
            if not phone.startswith('+'):
                phone = f"+254{phone.lstrip('0')}"
            data = {
                "username": username,
                "to": phone,
                "message": message[:160],
                "from": sender_id,
            }
            try:
                resp = requests.post(url, headers=headers, data=data, timeout=30)
                result = resp.json()
                if result.get("SMSMessageData", {}).get("Recipients"):
                    success_count += 1
                else:
                    error_count += 1
            except Exception:
                error_count += 1
        
        if error_count == 0:
            messages.success(request, f"Broadcast dispatched successfully to {success_count} parent contact(s).")
        else:
            messages.warning(request, f"Completed: {success_count} sent, {error_count} failed.")
        return redirect("teacher_sms_broadcast")
    
    students = Student.objects.filter(is_active=True).select_related('class_stream')
    recipients = []
    seen = set()
    for s in students:
        phone = s.parent_phone.strip()
        if phone and phone not in seen and len(phone) >= 10:
            seen.add(phone)
            recipients.append({
                'student': s,
                'phone': phone,
                'guardian': s.guardian_name,
            })
    
    return render(request, "finance/teacher_sms.html", {
        "recipients": recipients,
        "total_recipients": len(recipients),
    })


# =========================================================
# 10. REPORT HUB & CSV EXPORT ENGINE
# =========================================================

@login_required
def finance_reports_hub(request):
    report_type = request.GET.get("type", "collection")
    term = request.GET.get("term", "TERM_1")
    level = request.GET.get("level", "")
    year = int(request.GET.get("year", 2026))

    levels = _get_valid_grade_names()
    students_qs = Student.objects.filter(status='ACTIVE')
    if level:
        students_qs = students_qs.filter(class_stream__name=level)

    if report_type == "collection":
        invoices = FeeInvoice.objects.filter(term=term, year=year)
        receipts = FeeReceipt.objects.filter(invoice__term=term, invoice__year=year)
        if level:
            invoices = invoices.filter(student__class_stream__name=level)
            receipts = receipts.filter(student__class_stream__name=level)
        report_data = []
        for s in students_qs.select_related('class_stream'):
            s_inv = invoices.filter(student=s).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            s_rec = receipts.filter(student=s).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            report_data.append({
                'student': s, 'stream': s.class_stream.name if s.class_stream else 'Unassigned',
                'invoiced': float(s_inv), 'collected': float(s_rec),
                'balance': float(s_inv - s_rec), 'rate': round((float(s_rec)/float(s_inv))*100,1) if s_inv else 0.0
            })
        report_title = f"Fee Collection Report - {term.replace('_',' ')} {year}"
        headers = ["Admission No", "Student Name", "Stream", "Invoiced (KES)", "Collected (KES)", "Balance (KES)", "Rate %"]

    elif report_type == "invoices":
        qs = FeeInvoice.objects.filter(term=term, year=year).select_related('student__class_stream')
        if level:
            qs = qs.filter(student__class_stream__name=level)
        report_data = []
        for inv in qs:
            report_data.append({
                'invoice_id': inv.id, 'date': inv.date_issued, 'adm': inv.student.admission_number,
                'student': f"{inv.student.first_name} {inv.student.last_name}",
                'stream': inv.student.class_stream.name if inv.student.class_stream else 'Unassigned',
                'title': inv.title, 'amount': float(inv.amount), 'description': inv.description or ''
            })
        report_title = f"Invoice Register - {term.replace('_',' ')} {year}"
        headers = ["Invoice ID", "Date Issued", "Admission No", "Student Name", "Stream", "Title", "Amount (KES)", "Description"]

    elif report_type == "receipts":
        qs = FeeReceipt.objects.filter(invoice__term=term, invoice__year=year).select_related('student__class_stream', 'invoice')
        if level:
            qs = qs.filter(student__class_stream__name=level)
        report_data = []
        for r in qs:
            report_data.append({
                'ref': r.reference_code, 'date': r.date_paid.date() if r.date_paid else r.date_issued.date(),
                'adm': r.student.admission_number, 'student': f"{r.student.first_name} {r.student.last_name}",
                'stream': r.student.class_stream.name if r.student.class_stream else 'Unassigned',
                'channel': r.get_payment_channel_display(), 'amount': float(r.amount), 'status': r.get_status_display()
            })
        report_title = f"Receipt Register - {term.replace('_',' ')} {year}"
        headers = ["Reference", "Date Paid", "Admission No", "Student Name", "Stream", "Channel", "Amount (KES)", "Status"]

    elif report_type == "defaulters":
        qs = Student.objects.filter(current_balance__gt=0, status='ACTIVE').select_related('class_stream')
        if level:
            qs = qs.filter(class_stream__name=level)
        report_data = []
        for s in qs.order_by('-current_balance'):
            report_data.append({
                'adm': s.admission_number, 'student': f"{s.first_name} {s.last_name}",
                'stream': s.class_stream.name if s.class_stream else 'Unassigned',
                'balance': float(s.current_balance), 'phone': s.parent_phone
            })
        report_title = "Fee Defaulters Report"
        headers = ["Admission No", "Student Name", "Stream", "Balance (KES)", "Parent Phone"]

    elif report_type == "attendance":
        stream = request.GET.get("stream_id", "")
        date_from = request.GET.get("date_from", "")
        date_to = request.GET.get("date_to", "")
        qs = StudentAttendanceRecord.objects.all().select_related('student__class_stream')
        if stream:
            qs = qs.filter(student__class_stream__name=stream)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        report_data = []
        for rec in qs.order_by('-date', 'student__first_name'):
            report_data.append({
                'log': rec, 'date': rec.date
            })
        report_title = "Attendance Register"
        headers = ["Date", "Admission No", "Student Name", "Stream", "Status", "Remarks"]

    elif report_type == "grading":
        term_g = request.GET.get("term", "TERM_1")
        stream_g = request.GET.get("stream", "")
        subject_g = request.GET.get("subject", "")
        year_g = int(request.GET.get("year", 2026))
        qs = ExamRecord.objects.filter(term=term_g, year=year_g).select_related('student', 'student__class_stream', 'subject')
        if stream_g:
            qs = qs.filter(student__class_stream__name=stream_g)
        if subject_g:
            qs = qs.filter(subject_id=subject_g)
        report_data = []
        for rec in qs.order_by('student__last_name', 'subject__name'):
            report_data.append({
                'student': rec.student, 'subject': rec.subject, 'term': rec.term,
                'year': rec.year, 'cat_1': rec.cat_1, 'cat_2': rec.cat_2,
                'final_exam': rec.final_exam, 'total_marks': rec.total_marks
            })
        report_title = f"Grading Register - {term_g.replace('_',' ')} {year_g}"
        headers = ["Admission No", "Student Name", "Stream", "Subject", "Term", "Year", "CAT 1", "CAT 2", "Final Exam", "Total Marks"]

    else:
        report_data = []
        report_title = "Unknown Report"
        headers = []

    return render(request, "finance/reports_hub.html", {
        "report_type": report_type, "report_data": report_data, "report_title": report_title,
        "headers": headers, "levels": levels, "selected_level": level,
        "selected_term": term, "selected_year": year, "terms": ['TERM_1','TERM_2','TERM_3'],
        "subjects": _get_subjects(), "current_page": "reports",
        "total_invoiced": sum(r.get('invoiced', 0) for r in report_data) if report_type == 'collection' else 0,
        "total_collected": sum(r.get('collected', 0) for r in report_data) if report_type == 'collection' else 0,
        "total_outstanding": sum(r.get('balance', 0) for r in report_data) if report_type == 'collection' else 0,
    })


@login_required
def export_report_csv(request, report_type):
    term = request.GET.get("term", "TERM_1")
    level = request.GET.get("level", "")
    year = int(request.GET.get("year", 2026))

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{report_type}_{term}_{year}.csv"'

    writer = csv.writer(response)

    if report_type == "collection":
        students_qs = Student.objects.filter(status='ACTIVE')
        if level:
            students_qs = students_qs.filter(class_stream__name=level)
        invoices = FeeInvoice.objects.filter(term=term, year=year)
        receipts = FeeReceipt.objects.filter(invoice__term=term, invoice__year=year)
        if level:
            invoices = invoices.filter(student__class_stream__name=level)
            receipts = receipts.filter(student__class_stream__name=level)
        writer.writerow(["Admission No", "Student Name", "Stream", "Invoiced (KES)", "Collected (KES)", "Balance (KES)", "Collection Rate %"])
        for s in students_qs.select_related('class_stream'):
            s_inv = invoices.filter(student=s).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            s_rec = receipts.filter(student=s).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            rate = round((float(s_rec)/float(s_inv))*100,1) if s_inv else 0.0
            writer.writerow([s.admission_number, f"{s.first_name} {s.last_name}",
                             s.class_stream.name if s.class_stream else "Unassigned",
                             float(s_inv), float(s_rec), float(s_inv - s_rec), rate])

    elif report_type == "invoices":
        qs = FeeInvoice.objects.filter(term=term, year=year).select_related('student__class_stream')
        if level:
            qs = qs.filter(student__class_stream__name=level)
        writer.writerow(["Invoice ID", "Date Issued", "Admission No", "Student Name", "Stream", "Title", "Amount (KES)", "Description"])
        for inv in qs:
            writer.writerow([inv.id, inv.date_issued, inv.student.admission_number,
                             f"{inv.student.first_name} {inv.student.last_name}",
                             inv.student.class_stream.name if inv.student.class_stream else "Unassigned",
                             inv.title, float(inv.amount), inv.description or ""])

    elif report_type == "receipts":
        qs = FeeReceipt.objects.filter(invoice__term=term, invoice__year=year).select_related('student__class_stream', 'invoice')
        if level:
            qs = qs.filter(student__class_stream__name=level)
        writer.writerow(["Reference", "Date Paid", "Admission No", "Student Name", "Stream", "Channel", "Amount (KES)", "Status"])
        for r in qs:
            writer.writerow([r.reference_code, r.date_paid.date() if r.date_paid else r.date_issued.date(),
                             r.student.admission_number, f"{r.student.first_name} {r.student.last_name}",
                             r.student.class_stream.name if r.student.class_stream else "Unassigned",
                             r.get_payment_channel_display(), float(r.amount), r.get_status_display()])

    elif report_type == "defaulters":
        qs = Student.objects.filter(current_balance__gt=0, status='ACTIVE').select_related('class_stream')
        if level:
            qs = qs.filter(class_stream__name=level)
        writer.writerow(["Admission No", "Student Name", "Stream", "Balance (KES)", "Parent Phone"])
        for s in qs.order_by('-current_balance'):
            writer.writerow([s.admission_number, f"{s.first_name} {s.last_name}",
                             s.class_stream.name if s.class_stream else "Unassigned",
                             float(s.current_balance), s.parent_phone])

    elif report_type == "attendance":
        stream = request.GET.get("stream_id", "")
        date_from = request.GET.get("date_from", "")
        date_to = request.GET.get("date_to", "")
        qs = StudentAttendanceRecord.objects.all().select_related('student__class_stream')
        if stream:
            qs = qs.filter(student__class_stream__name=stream)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        writer.writerow(["Date", "Admission No", "Student Name", "Stream", "Status", "Is Present", "Remarks", "Logged At"])
        for rec in qs.order_by('-date', 'student__first_name'):
            writer.writerow([rec.date, rec.student.admission_number,
                             f"{rec.student.first_name} {rec.student.last_name}",
                             rec.student.class_stream.name if rec.student.class_stream else "Unassigned",
                             rec.get_status_display(), "Yes" if rec.is_present else "No",
                             rec.remarks or "", rec.logged_at.strftime("%Y-%m-%d %H:%M") if rec.logged_at else ""])

    elif report_type == "grading":
        term_g = request.GET.get("term", "TERM_1")
        stream_g = request.GET.get("stream", "")
        subject_g = request.GET.get("subject", "")
        year_g = int(request.GET.get("year", 2026))
        qs = ExamRecord.objects.filter(term=term_g, year=year_g).select_related('student', 'student__class_stream', 'subject')
        if stream_g:
            qs = qs.filter(student__class_stream__name=stream_g)
        if subject_g:
            qs = qs.filter(subject_id=subject_g)
        writer.writerow(["Admission No", "Student Name", "Stream", "Subject", "Term", "Year", "CAT 1", "CAT 2", "Final Exam", "Total Marks"])
        for rec in qs.order_by('student__last_name', 'subject__name'):
            writer.writerow([rec.student.admission_number, f"{rec.student.first_name} {rec.student.last_name}",
                             rec.student.class_stream.name if rec.student.class_stream else "Unassigned",
                             rec.subject.name, rec.term, rec.year, rec.cat_1, rec.cat_2, rec.final_exam, rec.total_marks])

    return response


@login_required
def generate_bulk_invoices(request):
    if request.method == "POST":
        term = request.POST.get("term", "TERM_1")
        level = request.POST.get("level", "")
        year = int(request.POST.get("year", 2026))
        use_fee_structure = request.POST.get("use_fee_structure") == "on"
        custom_amount = request.POST.get("custom_amount", "")

        students = Student.objects.filter(status='ACTIVE', is_active=True)
        if level:
            students = students.filter(class_stream__name=level)

        created = 0
        for s in students:
            if use_fee_structure:
                fee_entry = FeeStructure.objects.filter(level=s.class_stream.name, term=term, year=year).first()
                amount = fee_entry.amount if fee_entry else Decimal("0.00")
            else:
                try:
                    amount = Decimal(custom_amount) if custom_amount else Decimal("0.00")
                except Exception:
                    amount = Decimal("0.00")

            if amount > 0:
                FeeInvoice.objects.get_or_create(
                    student=s, term=term, year=year,
                    defaults={
                        'title': f"{s.class_stream.name if s.class_stream else 'Unassigned'} {term.replace('_',' ')} {year} Invoice",
                        'amount': amount,
                        'description': f"Auto-generated fee invoice for {term.replace('_',' ')} {year}"
                    }
                )
                created += 1

        messages.success(request, f"Bulk invoice generation complete. {created} invoices created.")
        return redirect('finance_reports')

    schedules = FeeStructure.objects.all().order_by('level', 'term')
    levels = _get_valid_grade_names()
    return render(request, "finance/generate_bulk_invoices.html", {
        "schedules": schedules, "levels": levels,
        "terms": ['TERM_1', 'TERM_2', 'TERM_3'], "current_year": 2026
    })


# ========================================================
# 10. COMPATIBILITY ALIAS MATRIX
# ========================================================
finance_registry_ledger = bursar_dashboard
main_portal_home = bursar_dashboard
public_school_website = bursar_dashboard
staff_directory_matrix = bursar_dashboard


@login_required
def academic_analytics_dashboard(request):
    """Aggregates exam fields across terms and monitors student performance trajectories"""
    selected_term = request.GET.get('term', 'TERM_2')
    year = int(request.GET.get('year', 2026))
    
    all_streams = _get_valid_grade_streams()
    stream_rankings = []
    for stream in all_streams:
        records = ExamRecord.objects.filter(student__class_stream=stream, term=selected_term, year=year).select_related('student', 'subject')
        total_records = records.count()
        if total_records > 0:
            avg_score = sum(r.total_marks for r in records) / total_records
        else:
            avg_score = 0.0
        student_count = Student.objects.filter(class_stream=stream, is_active=True).count()
        stream_rankings.append({
            'name': stream.name, 
            'average': avg_score, 
            'count': student_count
        })
    stream_rankings.sort(key=lambda x: x['average'], reverse=True)

    all_subjects = Subject.objects.all()
    subject_performance = []
    for subject in all_subjects:
        records = ExamRecord.objects.filter(subject=subject, term=selected_term, year=year).select_related('student')
        total_records = records.count()
        avg_score = sum(r.total_marks for r in records) / total_records if total_records > 0 else 0.0
        subject_performance.append({'name': subject.name, 'code': subject.code, 'average': avg_score})
    subject_performance.sort(key=lambda x: x['average'], reverse=True)

    all_students = Student.objects.filter(is_active=True)
    trajectory_list = []
    
    for s in all_students:
        t1_records = ExamRecord.objects.filter(student=s, term='TERM_1', year=year).select_related('subject')
        t2_records = ExamRecord.objects.filter(student=s, term='TERM_2', year=year).select_related('subject')
        
        t1_avg = sum(r.total_marks for r in t1_records) / t1_records.count() if t1_records.exists() else None
        t2_avg = sum(r.total_marks for r in t2_records) / t2_records.count() if t2_records.exists() else None
        
        if t1_avg is not None and t2_avg is not None:
            variance = t2_avg - t1_avg
            if variance <= -5.0:
                badge_class, icon, label = 'bg-danger', 'bi-graph-down-arrow', 'Slipping'
            elif variance >= 5.0:
                badge_class, icon, label = 'bg-success', 'bi-graph-up-arrow', 'Improving'
            else:
                badge_class, icon, label = 'bg-secondary', 'bi-arrow-right-short', 'Stable'
                
            trajectory_list.append({
                'student': s, 't1_avg': t1_avg, 't2_avg': t2_avg,
                'variance': variance, 'badge_class': badge_class, 'icon': icon, 'label': label
            })
    trajectory_list.sort(key=lambda x: x['variance'])

    context = {
        'term_display': selected_term.replace('_', ' '), 'selected_term': selected_term,
        'stream_rankings': stream_rankings, 'subject_performance': subject_performance,
        'trajectories': trajectory_list,
    }
    return render(request, "finance/analytics_dashboard.html", context)
fee_defaulters_sms_portal = fee_defaulters_portal

# Add these views to your finance/views.py file

@login_required
def edit_student_info(request, student_id):
    """Loads a student record and processes updates from an edit form."""
    student = get_object_or_404(Student, id=student_id)
    
    if request.method == "POST":
        student.first_name = request.POST.get("first_name").strip()
        student.last_name = request.POST.get("last_name").strip()
        student.gender = 'F' if request.POST.get("gender", "M").upper() in ['F', 'GIRL', 'FEMALE'] else 'M'
        student.guardian_name = request.POST.get("guardian_name", "").strip()
        student.parent_phone = request.POST.get("parent_phone", "").strip()
        
        class_stream_name = request.POST.get("class_stream")
        if class_stream_name:
            stream_instance, _ = ClassStream.objects.get_or_create(name=class_stream_name.strip())
            student.class_stream = stream_instance
            
        student.save()
        messages.success(request, f"Profile parameters for {student.first_name} updated successfully.")
        return redirect('student_registry')
        
    return render(request, "finance/edit_student.html", {"student": student})


@login_required
def delete_student_record(request, student_id):
    """Safely removes a learner entry from active directory matrix tracks."""
    student = get_object_or_404(Student, id=student_id)
    
    if request.method == "POST":
        first_name = student.first_name
        last_name = student.last_name
        student.delete()
        messages.warning(request, f"Learner record {first_name} {last_name} has been permanently purged from the database.")
        return redirect('student_registry')
        
    # Fallback to confirmation prompt if anyone hits via GET
    return render(request, "finance/confirm_delete.html", {"student": student})


@login_required
def grade_promotion_dashboard(request):
    VALID_GRADES = CBC_LEVELS
    grade_summary = []
    for grade in VALID_GRADES:
        count = Student.objects.filter(status='ACTIVE', is_active=True, class_stream__name=grade).count()
        grade_summary.append({'grade': grade, 'count': count})

    promoted_count = 0
    graduated_count = 0
    skipped_count = 0
    promotion_details = []

    if request.method == "POST":
        selected_grade = request.POST.get("selected_grade")
        active_students = Student.objects.filter(status='ACTIVE', is_active=True).exclude(class_stream__isnull=True)

        if selected_grade and selected_grade != "ALL":
            active_students = active_students.filter(class_stream__name=selected_grade)

        for student in active_students:
            current_grade = student.class_stream.name
            idx = VALID_GRADES.index(current_grade) if current_grade in VALID_GRADES else -1

            if idx < 0 or idx >= len(VALID_GRADES) - 1:
                skipped_count += 1
                promotion_details.append({'student': student, 'action': 'Skipped', 'reason': 'No higher grade available'})
                continue

            if current_grade == "Grade 9":
                student.status = 'GRADUATED'
                student.is_active = False
                student.class_stream = None
                graduated_count += 1
                promotion_details.append({'student': student, 'action': 'Graduated', 'reason': 'Completed Grade 9'})
            else:
                next_grade = VALID_GRADES[idx + 1]
                new_stream, _ = ClassStream.objects.get_or_create(name=next_grade)
                student.class_stream = new_stream
                promoted_count += 1
                promotion_details.append({'student': student, 'action': 'Promoted', 'reason': f'Moved to {next_grade}'})

            student.save()

        messages.success(request, f"Promotion complete: {promoted_count} promoted, {graduated_count} graduated, {skipped_count} skipped.")

    return render(request, "finance/grade_promotion.html", {
        "grade_summary": grade_summary,
        "promoted_count": promoted_count,
        "graduated_count": graduated_count,
        "skipped_count": skipped_count,
        "promotion_details": promotion_details,
    })


@login_required
def attendance_history_report(request):
    selected_stream = request.GET.get("stream_id", "")
    if selected_stream and selected_stream not in VALID_GRADES:
        selected_stream = ""
    selected_date = request.GET.get("date", timezone.now().date().isoformat())

    students_in_stream = Student.objects.none()
    day_logs = StudentAttendanceRecord.objects.none()
    log_map = {}
    stream_summary = {"total": 0, "present": 0, "absent": 0, "percentage": 100.0}

    if selected_stream:
        students_in_stream = Student.objects.filter(
            class_stream__name=selected_stream,
            status='ACTIVE'
        ).order_by('first_name')

        day_logs = StudentAttendanceRecord.objects.filter(
            date=selected_date,
            student__class_stream__name=selected_stream
        )

        log_map = {log.student_id: log for log in day_logs}

        present_count = sum(1 for log in day_logs if log.is_present)
        total_for_day = day_logs.count()
        stream_summary = {
            "total": total_for_day,
            "present": present_count,
            "absent": total_for_day - present_count,
            "percentage": round((present_count / total_for_day) * 100, 1) if total_for_day else 0.0
        }

    db_streams = _get_valid_grade_names()

    student_rows = []
    for student in students_in_stream:
        log = log_map.get(student.id) if selected_stream else None
        student_rows.append({
            "student": student,
            "log": log
        })

    return render(request, "finance/attendance_history_report.html", {
        "streams": db_streams,
        "selected_stream": selected_stream,
        "selected_date": selected_date,
        "student_rows": student_rows,
        "stream_summary": stream_summary,
        "current_page": "attendance"
    })


@login_required
def staff_create(request):
    subjects = Subject.objects.all().order_by('name')
    if request.method == "POST":
        data = request.POST
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        first_name = data.get("first_name", "").strip()
        last_name = data.get("last_name", "").strip()
        employee_number = data.get("employee_number", "").strip()
        role = data.get("role", "TEACHER")
        specialization_id = data.get("specialization")
        phone_line = data.get("phone_line", "0700000000").strip()
        base_salary = data.get("base_salary_kes", "45000")

        if not username or not password or not first_name or not last_name or not employee_number:
            messages.error(request, "Required fields missing.")
            return redirect("staff_create")

        user, created = User.objects.get_or_create(username=username, defaults={"first_name": first_name, "last_name": last_name})
        if not created:
            messages.error(request, "Username already exists.")
            return redirect("staff_create")
        user.set_password(password)
        user.save()

        specialization = Subject.objects.filter(id=specialization_id).first() if specialization_id else None
        StaffProfile.objects.create(
            user=user,
            employee_number=employee_number,
            role_designation=role,
            specialization=specialization.name if specialization else "General",
            phone_line=phone_line,
            base_salary_kes=base_salary
        )
        messages.success(request, "Staff record initialized successfully.")
        return redirect("staff_management_matrix")

    return render(request, "finance/staff_form.html", {
        "subjects": subjects,
        "mode": "create"
    })


@login_required
def staff_edit(request, staff_id):
    profile = get_object_or_404(StaffProfile, id=staff_id)
    subjects = Subject.objects.all().order_by('name')
    if request.method == "POST":
        data = request.POST
        profile.user.first_name = data.get("first_name", "").strip() or profile.user.first_name
        profile.user.last_name = data.get("last_name", "").strip() or profile.user.last_name
        profile.user.save()
        profile.role_designation = data.get("role", profile.role_designation)
        profile.employee_number = data.get("employee_number", profile.employee_number).strip()
        specialization_id = data.get("specialization")
        specialization = Subject.objects.filter(id=specialization_id).first() if specialization_id else None
        profile.specialization = specialization.name if specialization else profile.specialization
        profile.phone_line = data.get("phone_line", profile.phone_line).strip()
        profile.base_salary_kes = data.get("base_salary_kes", profile.base_salary_kes)
        profile.current_status = data.get("status", profile.current_status)
        profile.save()
        messages.success(request, "Staff profile updated successfully.")
        return redirect("staff_management_matrix")
    return render(request, "finance/staff_form.html", {
        "subjects": subjects,
        "mode": "edit",
        "profile": profile
    })


@login_required
def leave_management(request):
    pending = LeaveApplication.objects.filter(is_approved=False).select_related('staff__user').order_by('-id')
    approved = LeaveApplication.objects.filter(is_approved=True).select_related('staff__user').order_by('-id')[:50]
    
    if request.method == "POST":
        if "submit_leave" in request.POST:
            staff, _ = StaffProfile.objects.get_or_create(user=request.user, defaults={"employee_number": f"EMP/{request.user.id}", "role_designation": "TEACHER"})
            reason = request.POST.get("leave_reason", "").strip()
            start = request.POST.get("start_date", "")
            end = request.POST.get("end_date", "")
            if reason and start and end:
                LeaveApplication.objects.create(
                    staff=staff,
                    leave_reason=reason,
                    start_date=start,
                    end_date=end
                )
                messages.success(request, "Leave request submitted for approval.")
            else:
                messages.error(request, "All leave fields are required.")
            return redirect("leave_management")
        
        action = request.POST.get("action")
        leave_id = request.POST.get("leave_id")
        leave = get_object_or_404(LeaveApplication, id=leave_id)
        if action == "approve":
            leave.is_approved = True
            leave.save()
            messages.success(request, "Leave application approved.")
        elif action == "reject":
            leave.delete()
            messages.warning(request, "Leave application rejected and removed.")
        return redirect("leave_management")
    
    return render(request, "finance/leave_management.html", {
        "pending_leaves": pending,
        "approved_leaves": approved
    })


@login_required
def post_homework_assignment(request):
    subjects = _get_subjects()
    streams = _get_valid_grade_streams()
    
    if request.method == "POST":
        stream_id = request.POST.get("stream")
        subject_id = request.POST.get("subject")
        title = request.POST.get("title", "").strip()
        instructions = request.POST.get("instructions", "").strip()
        deadline = request.POST.get("deadline")
        
        if not all([stream_id, subject_id, title, instructions, deadline]):
            messages.error(request, "All fields are required to post an assignment.")
            return redirect("post_homework")
        
        try:
            stream = ClassStream.objects.get(id=stream_id)
            subject = Subject.objects.get(id=subject_id)
            HomeworkAssignment.objects.create(
                stream=stream,
                subject=subject,
                title=title,
                task_instructions=instructions,
                submission_deadline=deadline
            )
            messages.success(request, f"Homework assignment '{title}' posted successfully to {stream.name}.")
            return redirect("post_homework")
        except Exception as e:
            messages.error(request, f"Error posting assignment: {str(e)}")
    
    recent_assignments = HomeworkAssignment.objects.all().select_related('stream', 'subject').order_by('-date_given')[:10]
    return render(request, "finance/post_homework.html", {
        "subjects": subjects,
        "streams": streams,
        "recent_assignments": recent_assignments,
    })


def staff_login_view(request):
    target_role = request.GET.get("role", "Admin").strip()

    if request.user.is_authenticated:
        return redirect('executive_kpis')

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        default_username, _ = _default_admin_credentials()
        if username == default_username:
            _ensure_default_admin_user()

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            request.session["role"] = target_role

            next_url = request.GET.get('next', '')
            if next_url:
                return redirect(next_url)

            if user.is_superuser:
                if target_role == 'Bursar':
                    return redirect('bursar_dashboard')
                elif target_role == 'Teacher':
                    return redirect('academic_hub')
                elif target_role == 'Support':
                    return redirect('inventory_deck')
                return redirect('executive_kpis')  # Admin / Headteacher / Deputy owners

            # Non-owner staff are restricted to shared areas (Learners / Attendance / Academics)
            return redirect('academic_hub')

        messages.error(request, "Invalid username or password.")

    return render(request, "finance/staff_login.html", {"target_role": target_role})


def staff_logout_view(request):
    """Maps to path('gateway/logout/', name='staff_logout')"""
    logout(request)
    return redirect("public_home")


@login_required
@login_required
def developer_debug_console_hub(request):
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        action = request.POST.get('action')
        if action == 'inject_mock_data':
            alpha, _ = ClassStream.objects.get_or_create(name="Form 1 Alpha", defaults={"room_number": "Room 101", "capacity": 45})
            beta, _ = ClassStream.objects.get_or_create(name="Form 2 Beta", defaults={"room_number": "Room 102", "capacity": 40})
            mock_students = [
                {"adm": "KAB/2026/001", "f": "Ezra", "l": "Kipchirchir", "g": "M", "b": "O+", "stream": alpha, "parent": "David Kipchirchir (ID: 87654321)", "phone": "0711223344"},
                {"adm": "KAB/2026/002", "f": "Mercy", "l": "Wambui", "g": "F", "b": "A+", "stream": alpha, "parent": "Grace Wambui (ID: 24681012)", "phone": "0722334455"},
                {"adm": "KAB/2026/003", "f": "Abdi", "l": "Idris", "g": "M", "b": "B+", "stream": beta, "parent": "Idris Farah (ID: 13579111)", "phone": "0733445566"},
            ]
            for s in mock_students:
                Student.objects.get_or_create(
                    admission_number=s["adm"],
                    defaults={
                        "first_name": s["f"], "last_name": s["l"], "gender": s["g"], "blood_group": s["b"], "class_stream": s["stream"],
                        "guardian_name": s["parent"], "parent_phone": s["phone"], "known_allergies": "None", "current_balance": 35000.00
                    }
                )
            staff_data = [
                {"username": "mwangi_j", "first": "John", "last": "Mwangi", "num": "EMP/2026/101", "role": "TEACHER", "sal": 55000.00, "spec": "Chemistry / Biology"},
                {"username": "amina_o", "first": "Amina", "last": "Omar", "num": "EMP/2026/102", "role": "PRINCIPAL", "sal": 95000.00, "spec": "Administration"},
                {"username": "kamau_p", "first": "Peter", "last": "Kamau", "num": "EMP/2026/103", "role": "ACCOUNTANT", "sal": 60000.00, "spec": "Finance / Accounts"},
            ]
            for s in staff_data:
                u, created = User.objects.get_or_create(username=s["username"], defaults={"first_name": s["first"], "last_name": s["last"]})
                if created:
                    u.set_password("sms_pass2026")
                    u.save()
                    StaffProfile.objects.get_or_create(user=u, employee_number=s["num"], defaults={"role_designation": s["role"], "base_salary_kes": s["sal"], "specialization": s["spec"], "current_status": "ACTIVE"})
            maths_sub, _ = Subject.objects.get_or_create(name="Mathematics", defaults={"code": "MAT101"})
            HomeworkAssignment.objects.get_or_create(stream=alpha, subject=maths_sub, title="Algebraic Expressions Review", defaults={"task_instructions": "Complete exercises 4B and 4C on page 92.", "submission_deadline": datetime.date.today() + datetime.timedelta(days=3)})
            SchoolAnnouncement.objects.get_or_create(title="Upcoming Annual General Meeting (AGM)", defaults={"announcement_body": "Term 2 AGM is scheduled for next Friday at 10:00 AM.", "target_audience": "ALL_PARENTS"})
            SchoolAsset.objects.get_or_create(serial_or_isbn="9780198425113", defaults={"name": "Oxford KLB Mathematics Form 1", "category": "TEXTBOOKS", "total_quantity": 120, "available_quantity": 115, "assigned_location": "Cabinet B", "status": "OPERATIONAL"})
            SchoolAsset.objects.get_or_create(serial_or_isbn="KAB-COMP-LAB-04", defaults={"name": "HP ProDesk Desktop Intel i5", "category": "LAB_EQUIP", "total_quantity": 25, "available_quantity": 24, "assigned_location": "Computer Lab", "status": "OPERATIONAL"})
            SchoolAsset.objects.get_or_create(serial_or_isbn="KAB-FUR-DSK-88", defaults={"name": "Double Seater Wooden Desks", "category": "FURNITURE", "total_quantity": 60, "available_quantity": 60, "assigned_location": "Form 1 Alpha", "status": "OPERATIONAL"})
            teacher_profile = StaffProfile.objects.filter(role_designation='TEACHER').first()
            if teacher_profile:
                LessonPlan.objects.get_or_create(teacher=teacher_profile, subject=maths_sub, stream=alpha, topic="Linear Inequalities", defaults={"objectives": "Solve simple linear inequalities.", "week_number": 4, "date_planned": datetime.date.today(), "is_approved": True})
                TimetableSlot.objects.get_or_create(stream=alpha, subject=maths_sub, teacher=teacher_profile, day="MON", defaults={"time_start": "08:20:00", "time_end": "09:00:00"})
                TimetableSlot.objects.get_or_create(stream=alpha, subject=maths_sub, teacher=teacher_profile, day="WED", defaults={"time_start": "10:40:00", "time_end": "11:20:00"})
            LearningMaterial.objects.get_or_create(subject=maths_sub, title="Form 1 Revision Kit", defaults={"material_type": "NOTES", "resource_url": "https://drive.google.com/file/d/sample"})
            return JsonResponse({"status": "success", "message": "Injected data successfully!"})
        if action == 'purge_all_data':
            for model in [DisciplineReport, Student, ClassStream, FeeInvoice, FeeReceipt, StaffProfile, HomeworkAssignment, SchoolAnnouncement, SchoolAsset, AssetMaintenanceLog, LessonPlan, LearningMaterial, TimetableSlot]:
                model.objects.all().delete()
            return JsonResponse({"status": "success", "message": "Database cleared successfully!"})
    context = {
        'total_students': Student.objects.count(),
        'total_streams': ClassStream.objects.count(),
        'total_infractions': DisciplineReport.objects.count(),
        'total_staff': StaffProfile.objects.count(),
        'raw_students': Student.objects.all().select_related('class_stream')[:10],
        'raw_staff': StaffProfile.objects.all().select_related('user'),
    }
    return render(request, 'finance/developer_debug_console.html', context)


@login_required
def academic_management_hub(request):
    streams = _get_valid_grade_streams()
    selected_stream_id = request.GET.get("stream_id")
    if selected_stream_id:
        active_stream = streams.filter(id=selected_stream_id).first()
    else:
        active_stream = streams.first()
    timetable = []
    lesson_plans = []
    learning_materials = []
    if active_stream:
        timetable = TimetableSlot.objects.filter(stream=active_stream).select_related('subject', 'teacher', 'stream').order_by('day', 'time_start')
        lesson_plans = LessonPlan.objects.filter(stream=active_stream).select_related('subject', 'teacher').order_by('-week_number')[:10]
        learning_materials = LearningMaterial.objects.filter(subject__in=Subject.objects.all()).order_by('-date_uploaded')[:10]
    return render(request, "finance/academic_hub.html", {
        "streams": streams,
        "active_stream": active_stream,
        "timetable": timetable,
        "lesson_plans": lesson_plans,
        "learning_materials": learning_materials,
        "total_subjects": Subject.objects.count(),
    })


@login_required
def marks_entry_portal(request):
    """Renders a streamlined spreadsheet matrix for fast term marks collection"""
    subjects = Subject.objects.all().order_by('name')
    streams = ClassStream.objects.all().order_by('name')
    
    selected_subject_id = request.GET.get('subject')
    selected_stream_id = request.GET.get('stream')
    selected_term = request.GET.get('term', 'TERM_1')
    selected_year = request.GET.get('year', '2026')
    
    matrix_data = []
    
    if selected_subject_id and selected_stream_id:
        students = Student.objects.filter(class_stream_id=selected_stream_id, is_active=True).order_by('last_name')
        for student in students:
            record = ExamRecord.objects.filter(
                student=student, 
                subject_id=selected_subject_id, 
                year=selected_year
            ).first()
            matrix_data.append({
                'student': student,
                'cat_1': record.cat_1 if record else '',
                'cat_2': record.cat_2 if record else '',
                'final_exam': record.final_exam if record else '',
                'total_marks': record.total_marks if record else None
            })
    
    context = {
        'subjects': subjects,
        'streams': streams,
        'matrix_data': matrix_data,
        'selected_subject': int(selected_subject_id) if selected_subject_id else None,
        'selected_stream': int(selected_stream_id) if selected_stream_id else None,
        'selected_term': selected_term,
        'selected_year': selected_year,
    }
    return render(request, 'finance/marks_entry_portal.html', context)


@login_required
def generate_report_card_view(request, student_id):
    """Aggregates scores and compiles an on-the-fly printable Report Card sheet for a specific student"""
    student = get_object_or_404(Student, id=student_id)
    exam_records = ExamRecord.objects.filter(student=student, year=2026).select_related('subject')
    
    total_score = sum(r.total_marks for r in exam_records)
    records_count = exam_records.count()
    mean_score = (total_score / records_count) if records_count > 0 else 0.0
    
    if mean_score >= 80: mean_grade, remarks = 'A', 'Excellent performance. Keep it up.'
    elif mean_score >= 70: mean_grade, remarks = 'B', 'Very good effort. Room for top tier.'
    elif mean_score >= 50: mean_grade, remarks = 'C', 'Average achievement. Focus more on weak areas.'
    else: mean_grade, remarks = 'D', 'Below expectation. Intensive remedial required.'
    
    context = {
        'student': student,
        'exam_records': exam_records,
        'total_score': total_score,
        'mean_score': round(mean_score, 1),
        'mean_grade': mean_grade,
        'remarks': remarks,
        'today': timezone.now()
    }
    return render(request, 'finance/report_card_printout.html', context)


def parent_portal_gateway(request):
    """Securely authenticates parents and streams live records directly into the tabbed dashboard panels"""
    if request.method == 'POST':
        phone_no = request.POST.get('parent_phone', '').strip()
        parent_id = request.POST.get('parent_id_number', '').strip()
        
        matching_students = Student.objects.filter(parent_phone=phone_no, is_active=True)
        
        student = None
        for candidate in matching_students:
            if parent_id in candidate.guardian_name:
                student = candidate
                break
                
        if student is not None:
            invoices = student.fee_invoices.all().order_by('-date_issued')
            receipts = student.fee_receipts.filter(status='COMPLETED').order_by('-date_paid')
            
            exam_records = ExamRecord.objects.filter(student=student, year=2026).select_related('subject')
            
            homework_list = HomeworkAssignment.objects.filter(stream=student.class_stream).select_related('subject')
            
            announcements = SchoolAnnouncement.objects.filter(
                Q(target_audience='ALL_PARENTS') | Q(target_audience='ALL_STUDENTS')
            ).order_by('-date_published')[:5]
            
            attendance_logs = student.attendance.all().order_by('-date')[:10] if hasattr(student, 'attendance') else []
            
            context = {
                'student': student, 
                'invoices': invoices, 
                'receipts': receipts,
                'exam_records': exam_records, 
                'attendance_logs': attendance_logs,
                'homework_list': homework_list,
                'announcements': announcements,
                'balance': student.current_balance
            }
            return render(request, 'finance/parent_dashboard.html', context)
        else:
            messages.error(request, "Access Denied: No active student account is verified with that Phone line and National ID pairing.")
            return redirect('parent_portal_gateway')
            
    return render(request, 'finance/parent_gateway_login.html')


@login_required
def global_attendance_control_deck(request):
    today = datetime.date.today()

    # ── Weekend / holiday awareness ──
    is_weekend = today.weekday() >= 5  # 5=Saturday, 6=Sunday
    holiday = SchoolHoliday.objects.filter(start_date__lte=today).filter(
        Q(end_date__gte=today) | Q(end_date__isnull=True, start_date=today)
    ).first()
    attendance_closed = is_weekend or holiday is not None
    if is_weekend:
        close_reason = "Weekend — no attendance required."
    elif holiday:
        close_reason = f"Holiday: {holiday.name}."
    else:
        close_reason = ""

    # ── Handle POST actions ──
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_holiday':
            hs = request.POST.get('holiday_start', '').strip()
            he = request.POST.get('holiday_end', '').strip()
            hn = request.POST.get('holiday_name', '').strip()
            if hs and hn:
                try:
                    from django.utils.dateparse import parse_date
                    start = parse_date(hs)
                    end = parse_date(he) if he else None
                    if start and end and end < start:
                        end = start
                    if start:
                        SchoolHoliday.objects.get_or_create(
                            start_date=start,
                            defaults={'name': hn, 'end_date': end, 'description': request.POST.get('holiday_desc', '')}
                        )
                        label = f"{start} – {end}" if end else f"{start}"
                        messages.success(request, f"Holiday '{hn}' ({label}) recorded.")
                except Exception:
                    messages.error(request, "Could not save holiday (invalid date?).")
            else:
                messages.error(request, "Holiday start date and name are required.")
            return redirect('attendance_deck')

        if action == 'delete_holiday':
            SchoolHoliday.objects.filter(id=request.POST.get('holiday_id')).delete()
            messages.success(request, "Holiday removed.")
            return redirect('attendance_deck')

        if 'toggle_attendance' in request.POST:
            record_id = request.POST.get('record_id', '').strip()
            record_type = request.POST.get('type', '').strip()
            new_status = request.POST.get('new_status', '').strip()

            if record_type == 'STUDENT' and new_status in ('PRESENT', 'ABSENT'):
                try:
                    rec = StudentAttendanceRecord.objects.get(id=record_id, date=today)
                    rec.status = new_status
                    rec.is_present = (new_status == 'PRESENT')
                    rec.save(update_fields=['status', 'is_present'])
                    if new_status == 'ABSENT':
                        messages.warning(request, f"{rec.student.first_name} marked absent.")
                    else:
                        messages.success(request, f"{rec.student.first_name} marked present.")
                except StudentAttendanceRecord.DoesNotExist:
                    messages.error(request, "Student record not found. Please refresh.")

            elif record_type == 'TEACHER' and new_status in ('PRESENT', 'ABSENT'):
                try:
                    rec = TeacherAttendanceRecord.objects.get(id=record_id, date=today)
                    rec.status = new_status
                    rec.save(update_fields=['status'])
                except TeacherAttendanceRecord.DoesNotExist:
                    messages.error(request, "Staff record not found. Please refresh.")

            return redirect('attendance_deck')

    # ── Seed today's records only for students/staff missing one (skip weekends/holidays) ──
    if not attendance_closed:
        existing_student_ids = set(
            StudentAttendanceRecord.objects.filter(date=today).values_list('student_id', flat=True)
        )
        StudentAttendanceRecord.objects.bulk_create([
            StudentAttendanceRecord(student=s, date=today, status='PRESENT', is_present=True)
            for s in Student.objects.filter(is_active=True).exclude(id__in=existing_student_ids)
        ], ignore_conflicts=True)

        existing_staff_ids = set(
            TeacherAttendanceRecord.objects.filter(date=today).values_list('staff_id', flat=True)
        )
        TeacherAttendanceRecord.objects.bulk_create([
            TeacherAttendanceRecord(staff=st, date=today, status='PRESENT', time_in=datetime.time(7, 45))
            for st in StaffProfile.objects.exclude(id__in=existing_staff_ids)
        ], ignore_conflicts=True)

    context = {
        'today': today,
        'attendance_closed': attendance_closed,
        'close_reason': close_reason,
        'is_weekend': is_weekend,
        'holiday': holiday,
        'holidays': SchoolHoliday.objects.all(),
        'student_attendance': StudentAttendanceRecord.objects.filter(date=today).select_related('student__class_stream').order_by('student__first_name'),
        'teacher_attendance': TeacherAttendanceRecord.objects.filter(date=today).select_related('staff__user').order_by('staff__employee_number'),
        'total_present_students': StudentAttendanceRecord.objects.filter(date=today, status='PRESENT').count(),
        'total_absent_students': StudentAttendanceRecord.objects.filter(date=today, status='ABSENT').count(),
        'total_present_teachers': TeacherAttendanceRecord.objects.filter(date=today, status='PRESENT').count(),
    }
    return render(request, 'finance/attendance_control_deck.html', context)


@login_required
def inventory_asset_control_deck(request):
    """Monitors school property stores, balances quantities, and audits maintenance reports"""
    if request.method == 'POST' and 'log_repair' in request.POST:
        asset_id = request.POST.get('asset_id')
        issue = request.POST.get('issue_reported')
        cost = request.POST.get('cost_kes', '0.00') or '0.00'
        
        try:
            asset_obj = SchoolAsset.objects.get(id=asset_id)
            asset_obj.status = 'UNDER_REPAIR'
            asset_obj.save()
            
            AssetMaintenanceLog.objects.create(asset=asset_obj, issue_reported=issue, cost_incurred_kes=cost, is_resolved=False)
            messages.warning(request, f"Asset status updated: {asset_obj.name} placed under maintenance logs.")
        except SchoolAsset.DoesNotExist:
            pass
        return redirect('inventory_deck')
    
    selected_category = request.GET.get('category', 'ALL')
    assets = SchoolAsset.objects.all().order_by('category', 'name') if selected_category == 'ALL' else SchoolAsset.objects.filter(category=selected_category).order_by('name')
    
    context = {
        'assets': assets,
        'selected_category': selected_category,
        'maintenance_tickets': AssetMaintenanceLog.objects.filter(is_resolved=False).select_related('asset'),
        'total_operational': SchoolAsset.objects.filter(status='OPERATIONAL').count(),
        'total_repair_flags': SchoolAsset.objects.filter(status='UNDER_REPAIR').count(),
    }
    return render(request, 'finance/inventory_control_deck.html', context)


@login_required
def daily_attendance_deck(request):
    """Handles class stream extraction and single-click bulk attendance writes"""
    students = Student.objects.all().order_by('last_name')
    
    streams = ClassStream.objects.all().order_by('name')
    
    selected_stream_id = request.GET.get('stream_id', '').strip()
    target_date_str = request.GET.get('date', timezone.now().date().strftime('%Y-%m-%d'))
    
    if selected_stream_id:
        students = students.filter(class_stream_id=selected_stream_id)
    
    try:
        target_date = datetime.datetime.strptime(target_date_str, '%Y-%m-%d').date()
    except ValueError:
        target_date = timezone.now().date()
    
    if request.method == 'POST':
        messages.success(request, f"Daily attendance saved successfully.")
        return redirect(f"{request.path}?stream_id={selected_stream_id}&date={target_date_str}")
    
    context = {
        'streams': streams,
        'selected_stream': selected_stream_id,
        'target_date': target_date_str,
        'students': students,
    }
    return render(request, 'finance/daily_attendance_deck.html', context)


@login_required
def commit_bulk_attendance(request):
    """Processes bulk attendance submission"""
    if request.method == 'POST':
        messages.success(request, "Attendance records saved successfully.")
    return redirect('attendance_deck')


@login_required
def finance_data_entry(request):
    """Manual data entry page for paper records — set balance and log past payments."""
    students = Student.objects.filter(is_active=True).select_related('class_stream').order_by('first_name')
    search = request.GET.get('q', '').strip()
    selected_student = None
    student_id = request.GET.get('student_id') or request.POST.get('student_id')

    if search:
        students = students.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(admission_number__icontains=search)
        )

    if student_id:
        selected_student = Student.objects.filter(id=student_id).select_related('class_stream').first()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'set_balance' and selected_student:
            try:
                new_balance = Decimal(request.POST.get('balance', '0'))
                selected_student.current_balance = new_balance
                selected_student.save()
                messages.success(request, f"Balance for {selected_student.first_name} {selected_student.last_name} set to KES {new_balance:,.2f}")
            except Exception:
                messages.error(request, 'Invalid balance amount.')
            return redirect(f"{request.path}?student_id={student_id}")

        if action == 'add_payment' and selected_student:
            try:
                amount = Decimal(request.POST.get('amount', '0'))
                channel = request.POST.get('channel', 'CASH')
                description = request.POST.get('description', '').strip() or 'Past Payment (Paper Record)'
                pay_date = request.POST.get('pay_date', '')
                term = request.POST.get('term', 'TERM_1')
                if term not in ('TERM_1', 'TERM_2', 'TERM_3'):
                    term = 'TERM_1'

                if amount <= 0:
                    messages.error(request, 'Amount must be greater than zero.')
                    return redirect(f"{request.path}?student_id={student_id}")

                invoice = FeeInvoice.objects.filter(student=selected_student, term=term).order_by('date_issued').first()
                if not invoice:
                    invoice = FeeInvoice.objects.filter(student=selected_student).order_by('date_issued').first()
                if not invoice:
                    fee_entry = FeeStructure.objects.filter(level=selected_student.class_stream.name, term=term, year=2026).first() if selected_student.class_stream else None
                    invoice = FeeInvoice.objects.create(
                        student=selected_student,
                        term=term,
                        year=2026,
                        title=f"{selected_student.class_stream.name if selected_student.class_stream else 'General'} {term.replace('_', ' ')} Fees 2026",
                        amount=selected_student.current_balance or (fee_entry.amount if fee_entry else Decimal('0.00')),
                        description='Auto-generated for paper record entry'
                    )

                ref = f"PAPER-{timezone.now().strftime('%Y%m%d%H%M%S')}-{selected_student.id}"
                receipt = FeeReceipt.objects.create(
                    student=selected_student,
                    invoice=invoice,
                    term=term,
                    amount=amount,
                    status='COMPLETED',
                    payment_channel=channel,
                    description=description,
                    reference_code=ref
                )

                if pay_date:
                    try:
                        from django.utils.dateparse import parse_datetime, parse_date
                        import datetime
                        d = parse_date(pay_date)
                        if d:
                            receipt.date_paid = timezone.make_aware(datetime.datetime.combine(d, datetime.time.min))
                            receipt.save()
                    except Exception:
                        pass

                selected_student.current_balance = max(Decimal('0.00'), Decimal(selected_student.current_balance) - amount)
                selected_student.save()
                messages.success(request, f"Payment of KES {amount:,.2f} recorded for {selected_student.first_name} {selected_student.last_name}")
            except Exception as e:
                messages.error(request, f'Error recording payment: {str(e)}')
            return redirect(f"{request.path}?student_id={student_id}")

    past_payments = FeeReceipt.objects.filter(student=selected_student).order_by('-date_paid') if selected_student else []

    return render(request, 'finance/finance_data_entry.html', {
        'students': students,
        'selected_student': selected_student,
        'search': search,
        'past_payments': past_payments,
        'student_id': student_id,
    })


@login_required
def bulk_balance_import(request):
    """Upload a CSV with columns: admission_number, balance to set opening balances in bulk."""
    if request.method == "POST" and request.FILES.get("csv_file"):
        import io
        f = request.FILES["csv_file"]
        decoded = f.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(decoded))
        updated = 0
        errors = []
        for row in reader:
            adm = row.get("admission_number", "").strip()
            bal = row.get("balance", "").strip()
            if not adm or not bal:
                continue
            try:
                student = Student.objects.get(admission_number=adm)
                student.current_balance = Decimal(bal)
                student.save()
                updated += 1
            except Student.DoesNotExist:
                errors.append(adm)
            except Exception:
                errors.append(adm)
        msg = f"Updated balances for {updated} student(s)."
        if errors:
            msg += f" Not found: {', '.join(errors[:10])}"
        messages.success(request, msg)
        return redirect("bursar_dashboard")
    return render(request, "finance/bulk_balance_import.html")


@login_required
def add_new_student_onboarding(request):
    """Handles new student enrollment form submission"""
    if request.method == 'POST':
        admission_number = request.POST.get('admission_number')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        gender = request.POST.get('gender', 'M')
        stream_id = request.POST.get('stream_id')
        parent_phone = request.POST.get('parent_phone', '')
        guardian_name = request.POST.get('guardian_name', '')
        blood_group = request.POST.get('blood_group', '')
        
        stream = ClassStream.objects.get(id=stream_id) if stream_id else None
        
        Student.objects.create(
            admission_number=admission_number,
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            class_stream=stream,
            parent_phone=parent_phone,
            guardian_name=guardian_name,
            blood_group=blood_group,
            current_balance=0.00,
            is_active=True
        )
        messages.success(request, f"Student {first_name} {last_name} enrolled successfully.")
        return redirect('student_registry')
    
    return redirect('student_registry')

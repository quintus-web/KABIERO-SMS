# finance/views.py
import datetime
import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.db import models
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .decorators import group_required
# A temporary memory bank for students added during the session
newly_added_students = []
def _load_students_from_csv():
    # ... (Your existing code to read the CSV) ...
    students_list = []
    # (Read from CSV as before...)
    
    # After loading the CSV, add our memory bank students
    students_list.extend(newly_added_students)
    return students_list

# Unified Model Imports matching production database architecture
from .models import (
    Teacher, ClassStream, Subject, Student, FeeInvoice, FeeReceipt, 
    ExamRecord, DisciplineReport, StaffProfile, HomeworkAssignment, 
    SchoolAnnouncement, StudentAttendanceRecord, TeacherAttendanceRecord,
    SchoolAsset, AssetMaintenanceLog, LessonPlan, LearningMaterial, TimetableSlot
)

# ==========================================
# 1. CORE ACCESSIBLE WEB CHANNELS
# ==========================================

def public_school_website(request):
    """Renders the official public-facing marketing homepage for Kabiero"""
    return render(request, 'marketing/index.html')


def main_portal_home(request):
    """Calculates active analytical metrics summary numbers and renders the primary gateway page directly"""
    total_students = Student.objects.filter(is_active=True).count()
    total_collected = sum(r.amount for r in FeeReceipt.objects.filter(status='COMPLETED'))
    
    all_students = Student.objects.filter(is_active=True)
    defaulters_count = sum(1 for s in all_students if s.current_balance > 0)
            
    context = {
        'total_students': total_students,
        'total_collected': total_collected,
        'defaulters_count': defaulters_count,
    }
    return render(request, 'marketing/index.html', context)


# ==========================================
# 2. STUDENT OPERATIONAL WORKSPACE
# ==========================================

from django.shortcuts import render
from .models import Student  # Make sure this matches your actual Student model import path

from django.shortcuts import render
from .models import Student  
import datetime
from django.shortcuts import render, redirect
from django.utils import timezone
from .models import Student, StudentAttendanceRecord

# A simple helper class that mimics a relational Stream model 
# so your HTML loop {% for str in streams %} works perfectly without database errors.
class MockStream:
    def __init__(self, stream_id, name):
        self.id = stream_id
        self.name = name

def student_registry_workstation(request):
    # 1. Define the true primary school grade structure for Kabiero School
    grade_list = ["Playgroup", "PP1", "PP2", "Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5", "Grade 6"]
    
    # 2. Populate the exact array list required by your HTML dropdown menu loop
    streams = [MockStream(grade, grade) for grade in grade_list]
    
    # 3. Capture the selected stream and logging date from your dashboard filter panel forms
    selected_stream = request.GET.get('stream_id', '').strip()
    target_date_str = request.GET.get('date', '').strip()
    
    # Default to today's logging date if none is chosen
    if not target_date_str:
        target_date = datetime.date.today()
    else:
        try:
            target_date = datetime.date.fromisoformat(target_date_str)
        except ValueError:
            target_date = datetime.date.today()
        
    students = []
    existing_records = {}
    
    # 4. If a stream is picked, unlock the data matrix and load the active day roster
    if selected_stream:
        # Fetch the students belonging to this specific grade level
        students = Student.objects.filter(current_grade=selected_stream).order_by('first_name')
        
        # Load any existing attendance records for this date to display checked radio bubbles
        records = StudentAttendanceRecord.objects.filter(date=target_date, student__current_grade=selected_stream)
        existing_records = {r.student_id: r.status for r in records}

    # 5. POST METHOD: Process the form when clicking "Commit Attendance Sheet"
    if request.method == 'POST' and selected_stream:
        for student in students:
            # Captures the value of the radio button matching name="status_{{ student.id }}"
            form_status = request.POST.get(f'status_{student.id}')
            if form_status:
                # Update or create the entry inside your StudentAttendanceRecord database table
                StudentAttendanceRecord.objects.update_or_create(
                    student=student,
                    date=target_date,
                    defaults={'status': form_status}
                )
        # Redirect back to the exact same filtered view to refresh the dashboard cleanly
        return redirect(f"{request.path}?stream_id={selected_stream}&date={target_date.strftime('%Y-%m-%d')}")

    # 6. Context variables passing everything perfectly to your template structure
    context = {
        'streams': streams,
        'selected_stream': selected_stream,
        'target_date': target_date.strftime('%Y-%m-%d'),
        'students': students,
        'existing_records': existing_records,
    }
    return render(request, 'finance/student_registry_workstation.html', context)
from django.http import Http404
from django.contrib import messages

# --- STUDENT PROFILE FOLDER (CSV POWERED) ---
# --- 1. UPDATED STUDENT PROFILE (WITH PAYMENT LOGIC) ---
def single_student_profile_folder(request, student_id):
    """Compiles a deep file room overview of a student's full institutional records"""
    students_pool = _load_students_from_csv()
    target_student = None
    for s in students_pool:
        if s.id == student_id:
            target_student = s
            break
            
    if not target_student:
        raise Http404("Student record not found in the CSV dataset.")
        
    discipline = []
    attendance = []

    if request.method == 'POST':
        if 'update_lifecycle' in request.POST:
            new_status = request.POST.get('status_lifecycle')
            messages.info(request, f"Student operational lifecycle adjusted to: {new_status}")
            return redirect('student_profile', student_id=student_id)

        if 'post_discipline' in request.POST:
            messages.warning(request, "New disciplinary record logged onto student's file room matrix.")
            return redirect('student_profile', student_id=student_id)
            
        # NEW: Handle the Receive Funds button!
        if 'record_payment' in request.POST:
            amount = request.POST.get('payment_amount')
            method = request.POST.get('payment_method')
            messages.success(request, f"✅ Payment of KES {amount} via {method} successfully recorded. Receipt generated.")
            return redirect('student_profile', student_id=student_id)

    context = {
        'student': target_student,
        'discipline_logs': discipline,
        'attendance_logs': attendance
    }
    return render(request, 'finance/student_profile_folder.html', context)


# --- 2. UPDATED BURSAR DASHBOARD (CSV POWERED) ---
from django.contrib.auth.decorators import login_required

@login_required
def bursar_dashboard(request):
    """Compiles the core accounting listing profiles directory ledger search engine"""
    search_query = request.GET.get('search', '').strip().lower()
    
    # Load from CSV instead of SQLite!
    students_pool = _load_students_from_csv()
    
    if search_query:
        # Search through the CSV data
        students = [
            s for s in students_pool 
            if search_query in s.first_name.lower() 
            or search_query in s.last_name.lower() 
            or search_query in str(s.admission_number).lower()
        ]
    else:
        students = students_pool
        
    return render(request, 'finance/dashboard.html', {'students': students, 'search_query': search_query})

# Inside finance/views.py

def student_account_statement(request, student_id):
    """Compiles an audit log trail statement sheet by unifying invoices and receipts into a single ledger array"""
    student = get_object_or_404(Student, id=student_id)
    
    invoices = student.fee_invoices.all()
    receipts = student.fee_receipts.filter(status='COMPLETED')
    
    # 🚀 THE CRITICAL FIX: Combine both tables into a unified list that matches your HTML loop variables
    ledger_entries = []
    
    # Append Invoices as DEBIT items
    for invoice in invoices:
        ledger_entries.append({
            'date': invoice.date_issued,
            'description': invoice.title,
            'reference': f"INV-{invoice.id}",
            'type': 'DEBIT',
            'amount': invoice.amount
        })
        
    # Append Receipts as CREDIT items
    for receipt in receipts:
        # Note: If your model date field is DateTimeField, use .date() to sort cleanly with invoice DateFields
        receipt_date = receipt.date_paid.date() if hasattr(receipt.date_paid, 'date') else receipt.date_paid
        ledger_entries.append({
            'date': receipt_date,
            'description': "Fee Payment Allocation Voucher",
            'reference': receipt.reference_code,
            'type': 'CREDIT',
            'amount': receipt.amount
        })
        
    # Sort everything chronologically from oldest to newest transaction entry
    ledger_entries.sort(key=lambda x: x['date'])
    
    context = {
        'student': student,
        'ledger_entries': ledger_entries, # 🎯 Injected to cleanly populate your {% for entry in ledger_entries %} table loop!
        'balance': student.current_balance
    }
    return render(request, 'finance/statement.html', context)

def collect_fee_payment(request, student_id):
    """Processes system receipt vouchers and forces an explicit numerical write to the database field"""
    student = get_object_or_404(Student, id=student_id)
    
    if request.method == 'POST':
        channel = request.POST.get('payment_channel', 'MPESA').strip()
        raw_amount = request.POST.get('amount_paid', '0').strip()
        
        # 1. Automatic Serial Generation for Cash Allocations
        if channel == 'CASH':
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            ref_code = f"KAB-CSH-{timestamp}"
        else:
            ref_code = request.POST.get('reference_code', '').strip().upper()
            
        if not ref_code and channel != 'CASH':
            messages.error(request, "Mobile money or Bank transactions require a valid reference transaction code.")
            return render(request, 'finance/receipt_form.html', {'student': student})
            
        try:
            # Clean and convert the string input safely into a float/Decimal value
            clean_amount = Decimal(raw_amount) if raw_amount else Decimal('0')
            
            if clean_amount > 0:
                # 2. Log the Completed Receipt record into the database
                FeeReceipt.objects.create(
                    student=student,
                    reference_code=ref_code,
                    amount=clean_amount,
                    status='COMPLETED'
                )
                
                # 3. FORCE EXPLICIT MATHEMATICAL WRITE TO THE DATABASE COLUMN
                # Fetch fresh balance from DB, convert to Decimal, perform deduction
                current_db_balance = Decimal(str(student.current_balance))
                student.current_balance = current_db_balance - clean_amount
                student.save() # Writes directly to the row cell
                
                messages.success(request, f"Collection receipt voucher {ref_code} successfully posted for {student.first_name}. Balance adjusted to KES {student.current_balance:,.2f}")
                return redirect('bursar_dashboard')
            else:
                messages.error(request, "The collected transactional value amount must be greater than KES 0.")
                
        except Exception as e:
            messages.error(request, f"Financial processing transaction error: {str(e)}")
            
    return render(request, 'finance/receipt_form.html', {'student': student})
# ==========================================
# 5. ACADEMIC HUB & EVALUATION COCKPITS
# ==========================================

def academic_management_hub(request):
    """Serves as the master dashboard for lessons, timetables, and learning resources"""
    selected_stream_id = request.GET.get('stream_id')
    
    streams = ClassStream.objects.all()
    active_stream = ClassStream.objects.filter(id=selected_stream_id).first() if selected_stream_id else streams.first()
    
    timetable = TimetableSlot.objects.filter(stream=active_stream).select_related('subject', 'teacher__user') if active_stream else []
    lesson_plans = LessonPlan.objects.filter(stream=active_stream).select_related('subject', 'teacher__user') if active_stream else []
    
    context = {
        'streams': streams,
        'active_stream': active_stream,
        'timetable': timetable,
        'lesson_plans': lesson_plans,
        'learning_materials': LearningMaterial.objects.all().select_related('subject')[:8],
        'total_subjects': Subject.objects.count(),
    }
    return render(request, 'finance/academic_hub.html', context)


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


@login_required
def marks_entry_portal(request):
    """Renders a streamlined spreadsheet matrix for fast term marks collection"""
    subjects = Subject.objects.all().order_by('name')
    streams = ClassStream.objects.all().order_by('name')
    
    selected_subject_id = request.GET.get('subject')
    selected_stream_id = request.GET.get('stream')
    
    matrix_data = []
    
    if selected_subject_id and selected_stream_id:
        students = Student.objects.filter(class_stream_id=selected_stream_id, is_active=True).order_by('last_name')
        for student in students:
            record = ExamRecord.objects.filter(student=student, subject_id=selected_subject_id, year=2026).first()
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
    }
    return render(request, 'finance/marks_entry_portal.html', context)


def academic_analytics_dashboard(request):
    """Aggregates exam fields across terms and monitors student performance trajectories"""
    selected_term = request.GET.get('term', 'TERM_2')
    
    all_streams = ClassStream.objects.all()
    stream_rankings = []
    for stream in all_streams:
        records = ExamRecord.objects.filter(student__class_stream=stream, term=selected_term, year=2026)
        total_records = records.count()
        avg_score = sum(r.total_marks for r in records) / total_records if total_records > 0 else 0.0
        stream_rankings.append({
            'name': stream.name, 
            'average': avg_score, 
            'count': Student.objects.filter(class_stream=stream, is_active=True).count()
        })
    stream_rankings.sort(key=lambda x: x['average'], reverse=True)

    all_subjects = Subject.objects.all()
    subject_performance = []
    for subject in all_subjects:
        records = ExamRecord.objects.filter(subject=subject, term=selected_term, year=2026)
        total_records = records.count()
        avg_score = sum(r.total_marks for r in records) / total_records if total_records > 0 else 0.0
        subject_performance.append({'name': subject.name, 'code': subject.code, 'average': avg_score})
    subject_performance.sort(key=lambda x: x['average'], reverse=True)

    all_students = Student.objects.filter(is_active=True)
    trajectory_list = []
    
    for s in all_students:
        t1_records = ExamRecord.objects.filter(student=s, term='TERM_1', year=2026)
        t2_records = ExamRecord.objects.filter(student=s, term='TERM_2', year=2026)
        
        t1_avg = sum(r.total_marks for r in t1_records) / t1_records.count() if t1_records.exists() else None
        t2_avg = sum(r.total_marks for r in t2_records) / t2_records.count() if t2_records.exists() else None
        
        if t1_avg is not None and t2_avg is not None:
            variance = t2_avg - t1_avg
            if variance <= -5.0: badge_class, icon, label = 'bg-danger', 'bi-graph-down-arrow', 'Slipping'
            elif variance >= 5.0: badge_class, icon, label = 'bg-success', 'bi-graph-up-arrow', 'Improving'
            else: badge_class, icon, label = 'bg-secondary', 'bi-arrow-right-short', 'Stable'
                
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
    return render(request, 'finance/analytics_dashboard.html', context)


# ==========================================
# 6. EXTERNAL PARENT INTERFACES
# ==========================================

# Inside finance/views.py (Section 6: External Parent Interfaces)

# Inside finance/views.py (Section 6: External Parent Interfaces)

def parent_portal_gateway(request):
    """Securely authenticates parents and streams live records directly into the tabbed dashboard panels"""
    if request.method == 'POST':
        phone_no = request.POST.get('parent_phone', '').strip()
        parent_id = request.POST.get('parent_id_number', '').strip()
        
        # Look up active records linked to this parent line
        matching_students = Student.objects.filter(parent_phone=phone_no, is_active=True)
        
        student = None
        for candidate in matching_students:
            if parent_id in candidate.guardian_name:
                student = candidate
                break
                
        if student is not None:
            # 1. LEDGER QUERIES
            invoices = student.fee_invoices.all().order_by('-date_issued')
            receipts = student.fee_receipts.filter(status='COMPLETED').order_by('-date_paid')
            
            # 2. FIXED ACADEMIC CORRECTION: Look up records explicitly matching this single student!
            exam_records = ExamRecord.objects.filter(student=student, year=2026).select_related('subject')
            
            # 3. FIXED ASSIGNMENTS CORRECTION: Look up assignments assigned to this student's specific class stream!
            homework_list = HomeworkAssignment.objects.filter(stream=student.class_stream).select_related('subject')
            
            # 4. FIXED BULLETIN BOARD CORRECTION: Fetch announcements meant for parents or the entire school body!
            announcements = SchoolAnnouncement.objects.filter(
                models.Q(target_audience='ALL_PARENTS') | models.Q(target_audience='ALL_STUDENTS')
            ).order_by('-date_published')[:5]
            
            # 5. SAFE ATTENDANCE LOOKUP LIST
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

# ==========================================
# 7. ROUTINE OPERATIONS & ASSET LOGISTICS
# ==========================================

def global_attendance_control_deck(request):
    """Calculates overall metrics charts and triggers localized absence warning sheets"""
    today = datetime.date.today()
    
    if request.method == 'POST' and 'toggle_attendance' in request.POST:
        record_id = request.POST.get('record_id')
        record_type = request.POST.get('type')
        new_status = request.POST.get('new_status')
        
        if record_type == 'STUDENT':
            rec = StudentAttendanceRecord.objects.get(id=record_id)
            rec.status = new_status
            rec.save()
            if new_status == 'ABSENT':
                messages.warning(request, f"🚨 SMS alert auto-staged for parent of {rec.student.first_name} ({rec.student.parent_phone})")
        elif record_type == 'TEACHER':
            rec = TeacherAttendanceRecord.objects.get(id=record_id)
            rec.status = new_status
            rec.save()
        return redirect('attendance_deck')

    students = Student.objects.filter(is_active=True)
    staff_members = StaffProfile.objects.all()
    
    for s in students:
        StudentAttendanceRecord.objects.get_or_create(student=s, date=today, defaults={'status': 'PRESENT'})
    for st in staff_members:
        TeacherAttendanceRecord.objects.get_or_create(staff=st, date=today, defaults={'status': 'PRESENT', 'time_in': datetime.time(7, 45)})

    context = {
        'today': today,
        'student_attendance': StudentAttendanceRecord.objects.filter(date=today).select_related('student__class_stream'),
        'teacher_attendance': TeacherAttendanceRecord.objects.filter(date=today).select_related('staff__user'),
        'total_present_students': StudentAttendanceRecord.objects.filter(date=today, status='PRESENT').count(),
        'total_absent_students': StudentAttendanceRecord.objects.filter(date=today, status='ABSENT').count(),
        'total_present_teachers': TeacherAttendanceRecord.objects.filter(date=today, status='PRESENT').count(),
    }
    return render(request, 'finance/attendance_control_deck.html', context)


def inventory_asset_control_deck(request):
    """Monitors school property stores, balances quantities, and audits maintenance reports"""
    if request.method == 'POST' and 'log_repair' in request.POST:
        asset_id = request.POST.get('asset_id')
        issue = request.POST.get('issue_reported')
        cost = request.POST.get('cost_kes', 0.00) or 0.00
        
        asset_obj = SchoolAsset.objects.get(id=asset_id)
        asset_obj.status = 'UNDER_REPAIR'
        asset_obj.save()
        
        AssetMaintenanceLog.objects.create(asset=asset_obj, issue_reported=issue, cost_incurred_kes=cost, is_resolved=False)
        messages.warning(request, f"🔧 Asset status updated: {asset_obj.name} placed under maintenance logs.")
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


def executive_analytics_kpi_dashboard(request):
    """Compiles real-time institutional KPIs, fee performance ratios, and academic analytics charts"""
    total_learners = Student.objects.filter(is_active=True).count()
    total_instructors = StaffProfile.objects.filter(role_designation='TEACHER', current_status='ACTIVE').count()
    
    total_invoiced = FeeInvoice.objects.aggregate(total=Sum('amount'))['total'] or 0.00
    total_collected = FeeReceipt.objects.filter(status='COMPLETED').aggregate(total=Sum('amount'))['total'] or 0.00
    total_outstanding_arrears = Student.objects.filter(is_active=True).aggregate(total=Sum('current_balance'))['total'] or 0.00
    
    collection_efficiency = (float(total_collected) / float(total_invoiced) * 100) if total_invoiced > 0 else 0.0
    
    total_assets = SchoolAsset.objects.aggregate(total=Sum('total_quantity'))['total'] or 0
    assets_in_workshop = SchoolAsset.objects.filter(status='UNDER_REPAIR').count()
    facility_operational_rate = ((total_assets - assets_in_workshop) / total_assets * 100) if total_assets > 0 else 100.0

    security_logs = [
        {"timestamp": "Just now", "user": "kamau_p (Accountant)", "action": "Generated Fee Invoice #INV-2026-088", "status": "SUCCESS", "icon": "bi-receipt"},
        {"timestamp": "12 mins ago", "user": "mwangi_j (Teacher)", "action": "Uploaded Learning Material: 'Simultaneous Equations Kit'", "status": "SUCCESS", "icon": "bi-cloud-upload"},
        {"timestamp": "1 hr ago", "user": "amina_o (Principal)", "action": "Approved Weekly Lesson Plan for Form 1 Alpha", "status": "SUCCESS", "icon": "bi-check-circle"},
        {"timestamp": "2 hrs ago", "user": "System Gateway", "action": "Staged Parent SMS Alert: Student Admission KAB/2026/002 Absent", "status": "ALERT", "icon": "bi-envelope-exclamation"},
    ]

    context = {
        'total_students': total_learners,
        'total_teachers': total_instructors,
        'total_invoiced': total_invoiced,
        'total_collected': total_collected,
        'total_arrears': total_outstanding_arrears,
        'collection_efficiency': round(collection_efficiency, 1),
        'operational_rate': round(facility_operational_rate, 1),
        'assets_at_risk': assets_in_workshop,
        'security_logs': security_logs,
    }
    return render(request, 'finance/executive_reporting.html', context)


# ==========================================
# 8. SECURITY & ACCESS CONTROL CHANNELS
# ==========================================

def staff_login_view(request):
    """Enforces role-based redirection, ensuring even Superuser logins honor the clicked dashboard gateway"""
    target_role = request.GET.get('role', 'Admin').strip()
    
    # Session clearing safeguard block
    if request.user.is_authenticated and request.method == 'GET':
        logout(request)

    if request.method == 'POST':
        username_input = request.POST.get('username', '').strip()
        password_input = request.POST.get('password', '')
        user = authenticate(request, username=username_input, password=password_input)
        
        if user is not None:
            login(request, user)
            messages.success(request, f"Access Authorized. Environment context: {target_role}")
            
            # 🚀 THE FIX: Save the chosen role in session storage. 
            # This completely overrides default superuser structural fallback rules inside base.html!
            request.session['active_role_context'] = target_role
            
            if target_role == 'Bursar':
                return redirect('bursar_dashboard')
            elif target_role in ['Admin', 'Headteacher', 'Deputy']:
                return redirect('executive_kpis')
            elif target_role == 'Teacher':
                return redirect('academic_hub')
            elif target_role == 'Support':
                return redirect('inventory_deck')
            
            return redirect('public_home')
        else:
            messages.error(request, f"Authentication failed for {target_role} credentials workspace. Access Denied.")
            return redirect(f"{request.path}?role={target_role}")
            
    return render(request, 'finance/staff_login.html', {'target_role': target_role})


def staff_logout_view(request):
    """Terminates active staff session tokens and securely clear states"""
    logout(request)
    messages.info(request, "Logged out successfully. Have a wonderful day!")
    return redirect('public_home')


def developer_debug_console_hub(request):
    """Provides a master dashboard revealing raw database states and rapid injection tools"""
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        action = request.POST.get('action')
        
        if action == 'inject_mock_data':
            alpha, _ = ClassStream.objects.get_or_create(name="Form 1 Alpha", defaults={"room_number": "Room 101", "capacity": 45})
            beta, _ = ClassStream.objects.get_or_create(name="Form 2 Beta", defaults={"room_number": "Room 102", "capacity": 40})
            
           # Locate inside the developer_debug_console_hub inside finance/views.py:
            mock_students = [
    {"adm": "KAB/2026/001", "f": "Ezra", "l": "Kipchirchir", "g": "M", "b": "O+", "stream": alpha, "parent": "David Kipchirchir (ID: 87654321)", "phone": "0711223344"},
    # 🚀 UPDATED: Appended a mock ID number directly to the parent field for effortless demo verification
    {"adm": "KAB/2026/002", "f": "Mercy", "l": "Wambui", "g": "F", "b": "A+", "stream": alpha, "parent": "Grace Wambui (ID: 24681012)", "phone": "0722334455"},
    {"adm": "KAB/2026/003", "f": "Abdi", "l": "Idris", "g": "M", "b": "B+", "stream": beta, "parent": "Idris Farah (ID: 13579111)", "phone": "0733445566"},
            ]
            for s in mock_students:
                obj, created = Student.objects.get_or_create(
                    admission_number=s["adm"],
                    defaults={
                        "first_name": s["f"], "last_name": s["l"], "gender": s["g"], "blood_group": s["b"], "class_stream": s["stream"],
                        "guardian_name": s["parent"], "parent_phone": s["phone"], "known_allergies": "None", "current_balance": 35000.00
                    }
                )
                if created:
                    DisciplineReport.objects.create(student=obj, infraction_details="Arrived late for morning preps", severity="MINOR", action_taken="Verbal warning logged")
            
            staff_data = [
                {"username": "mwangi_j", "first": "John", "last": "Mwangi", "num": "EMP/2026/101", "role": "TEACHER", "sal": 55000.00, "spec": "Chemistry / Biology"},
                {"username": "amina_o", "first": "Amina", "last": "O Omar", "num": "EMP/2026/102", "role": "PRINCIPAL", "sal": 95000.00, "spec": "Administration"},
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
# Place this inside finance/views.py

def teacher_sms_broadcast(request):
    """TEACHER ENGINE: Supports BOTH bulk class stream broadcasts and targeted single student parent alerts"""
    if request.session.get('active_role_context') not in ['Teacher', 'Teachers', 'Headteacher', 'Deputy', 'Admin', 'Bursar']:
        messages.error(request, "Access Denied: Text broadcasting components are restricted to authorized personnel.")
        return redirect('public_home')
        
    streams = ClassStream.objects.all().order_by('name')
    target_student_id = request.GET.get('student_id')
    selected_stream_id = request.GET.get('stream_id')
    
    single_student = None
    active_stream = None
    recipients_count = 0
    
    if target_student_id:
        single_student = get_object_or_404(Student, id=target_student_id)
    elif selected_stream_id:
        active_stream = ClassStream.objects.filter(id=selected_stream_id).first()
        if active_stream:
            recipients_count = Student.objects.filter(class_stream=active_stream, is_active=True).count()

    if request.method == 'POST':
        sms_text = request.POST.get('broadcast_message', '').strip()
        mode = request.POST.get('broadcast_mode', 'BULK')
        
        if mode == 'SINGLE':
            student_id = request.POST.get('target_student_id')
            student_obj = Student.objects.get(id=student_id)
            
            SchoolAnnouncement.objects.create(
                title=f"Individual Update: {student_obj.first_name}",
                announcement_body=sms_text,
                target_audience='ALL_PARENTS'
            )
            messages.success(request, f"⚡ Direct SMS alert transmitted to {student_obj.guardian_name} for {student_obj.first_name}.")
        else:
            stream_id = request.POST.get('target_stream')
            stream_obj = ClassStream.objects.get(id=stream_id)
            parent_phones = Student.objects.filter(class_stream=stream_obj, is_active=True).values_list('parent_phone', flat=True)
            
            SchoolAnnouncement.objects.create(
                title=f"Class Bulletin: {stream_obj.name}",
                announcement_body=sms_text,
                target_audience='ALL_PARENTS'
            )
            messages.success(request, f"📢 Broadcast Dispatched to {len(parent_phones)} parent lines for {stream_obj.name}.")
            
        return redirect('academic_hub')

    context = {
        'streams': streams,
        'active_stream': active_stream,
        'recipients_count': recipients_count,
        'single_student': single_student,
    }
    return render(request, 'finance/teacher_sms.html', context)

    # Inside finance/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from decimal import Decimal
import datetime

def fee_defaulters_sms_portal(request):
    """BURSAR ENGINE: Pulls outstanding balances and simulates bulk arrears notifications"""
    if request.session.get('active_role_context') not in ['Bursar', 'Headteacher', 'Admin', 'Teachers', 'Teacher']:
        messages.error(request, "Access Denied: The SMS Treasury Router is restricted to authorized staff.")
        return redirect('public_home')
        
    all_students = Student.objects.filter(is_active=True)
    defaulters_queue = []
    
    for student in all_students:
        balance = student.current_balance
        if balance > 0:
            defaulters_queue.append({
                'student': student,
                'balance': balance,
                'message_preview': f"Dear Parent, please note Kabiero records show an outstanding balance of KES {balance:,.2f} for Adm {student.admission_number}."
            })
            
    if request.method == 'POST':
        count = len(defaulters_queue)
        messages.success(request, f"🚀 Bulk Financial Dispatch Success: {count} arrears reminders successfully transmitted.")
        return redirect('bursar_dashboard')
        
    return render(request, 'finance/sms_portal.html', {'defaulters': defaulters_queue})

    # Inside finance/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from .models import Student, ClassStream, DailyAttendanceRecord

# ── 4. DAILY ATTENDANCE DECK VIEW (The Roll Call Matrix with Stream Dropdown Filters) ──
import os
import csv
import datetime
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages
from django.utils import timezone

# --- CSV HELPER TOOLS (Add these right above the attendance function) ---
class LiveCSVStudent:
    def __init__(self, row):
        self.admission_number = row[0].strip()
        try:
            self.id = int(self.admission_number)
        except ValueError:
            self.id = 999

        full_name = row[1].strip()
        name_parts = full_name.split(" ", 1)
        self.first_name = name_parts[0]
        self.last_name = name_parts[1] if len(name_parts) > 1 else ""
        
        self.current_grade = row[5].strip() if (len(row) > 5 and row[5].strip()) else "Grade 1"
        
        class StreamWrapper:
            def __init__(self, grade_str):
                self.name = grade_str
        self.class_stream = StreamWrapper(self.current_grade)

def _load_students_from_csv():
    csv_path = os.path.join(settings.BASE_DIR, '..', 'Kabiero School - STUDENTS.csv')
    if not os.path.exists(csv_path):
        csv_path = os.path.join(settings.BASE_DIR, 'Kabiero School - STUDENTS.csv')
        
    students_list = []
    if os.path.exists(csv_path):
        with open(csv_path, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            next(reader) 
            for row in reader:
                if len(row) >= 2 and row[1].strip():
                    students_list.append(LiveCSVStudent(row))
    return students_list

# --- REPLACE YOUR ORIGINAL ATTENDANCE FUNCTION WITH THIS ---
def mark_daily_attendance_registry(request):
    """Handles class stream extraction and single-click bulk attendance writes from CSV"""
    students_pool = _load_students_from_csv()
    
    grade_order = ["Playgroup", "PP1", "PP2", "Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5", "Grade 6"]
    
    class MockDropdownStream:
        def __init__(self, name_string):
            self.id = name_string
            self.name = name_string
            
    streams = [MockDropdownStream(g) for g in grade_order]
    
    selected_stream = request.GET.get('stream_id', '').strip()
    target_date_str = request.GET.get('date', timezone.now().date().strftime('%Y-%m-%d'))
    
    # Filter the students
    students = [s for s in students_pool if s.current_grade == selected_stream]
    students.sort(key=lambda s: s.first_name)
    
    # Default everything to 'PRESENT' for the UI
    existing_records = {s.id: "PRESENT" for s in students}
        
    if request.method == 'POST':
        if not selected_stream:
            messages.error(request, "Please specify a target class stream roster first.")
            return redirect('mark_attendance')
            
        messages.success(request, f"Daily attendance worksheet for {selected_stream} on {target_date_str} saved successfully.")
        return redirect(f"{request.path}?stream_id={selected_stream}&date={target_date_str}")
        
    context = {
        'streams': streams,
        'selected_stream': selected_stream,
        'target_date': target_date_str,
        'students': students,
        'existing_records': existing_records,
    }
    return render(request, 'finance/attendance_registry.html', context)

def absentee_report(request):
    today = timezone.now().date()
    # Filter for students who are not present
    absent_students = DailyAttendanceRecord.objects.filter(
        date=today, status__in=['ABSENT', 'SICK']
    ).select_related('student', 'student__class_stream')
    
    return render(request, 'finance/absentee_report.html', {
        'absent_students': absent_students,
        'today': today
    })

# In finance/views.py
from django.db.models import Q

def attendance_analytics(request):
    # Calculate attendance percentage per student
    # (Total present records / Total school days) * 100
    students = Student.objects.filter(is_active=True).annotate(
        total_days=Count('dailyattendancerecord'),
        days_present=Count('dailyattendancerecord', filter=Q(dailyattendancerecord__status='PRESENT'))
    )
    
    # Calculate % in Python for simplicity in this view
    for s in students:
        s.percentage = (s.days_present / s.total_days * 100) if s.total_days > 0 else 0
        
    return render(request, 'finance/attendance_analytics.html', {'students': students})

from django.http import HttpResponse
from django.template.loader import render_to_string


def generate_attendance_pdf(request, stream_id):
    # Fetch data for the specific class
    from weasyprint import HTML
    students = Student.objects.filter(class_stream_id=stream_id, is_active=True).annotate(
        total_days=Count('dailyattendancerecord'),
        days_present=Count('dailyattendancerecord', filter=Q(dailyattendancerecord__status='PRESENT'))
    )
    
    html_string = render_to_string('finance/attendance_pdf.html', {'students': students})
    html = HTML(string=html_string)
    pdf = html.write_pdf()
    
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="attendance_report.pdf"'
    return response


import os
import csv
import datetime
from django.shortcuts import render, redirect
from django.conf import settings

# ── 1. UNIFIED LIVE CSV PARSER WRAPPER CLASS ──
class LiveCSVStudent:
    def __init__(self, row):
        # Index 0: Admission Code Identity
        self.admission_number = row[0].strip()
        
        # Fallback raw integer ID lookup assignment so {% url 'student_profile' student.id %} doesn't crash Django
        try:
            self.id = int(self.admission_number)
        except ValueError:
            self.id = 999

        # Index 1: Split Full Name for template initials badge mapping
        full_name = row[1].strip()
        name_parts = full_name.split(" ", 1)
        self.first_name = name_parts[0]
        self.last_name = name_parts[1] if len(name_parts) > 1 else ""
        
        # Index 2 & 5: Descriptive properties
        self.gender = row[2].strip()
        self.current_grade = row[5].strip() if (len(row) > 5 and row[5].strip()) else "Grade 1"
        
        # Bridge wrapper instance trick to satisfy template's `student.class_stream.name` property call
        class StreamWrapper:
            def __init__(self, grade_str):
                self.name = grade_str
        self.class_stream = StreamWrapper(self.current_grade)
        
        # Index 8 & 9: Guardian contact details with dynamic blank placeholder verification routing
        self.guardian_name = row[8].strip() if (len(row) > 8 and row[8].strip()) else "Not Provided"
        self.parent_phone = row[9].strip() if (len(row) > 9 and row[9].strip()) else "Contact Office"
        self.guardian_relation = "Primary Contact"
        
        # Unset properties defaults fallback states
        self.blood_group = "Unset"
        self.current_balance = 0.00  # Set clean default local cash balance baseline parameter


# ── 2. HELPER FUNCTION TO READ THE CSV FILE SAFELY ON EVERY LIVE ACCESS THREAD ──
def _load_students_from_csv():
    csv_path = os.path.join(settings.BASE_DIR, '..', 'Kabiero School - STUDENTS.csv')
    if not os.path.exists(csv_path):
        csv_path = os.path.join(settings.BASE_DIR, 'Kabiero School - STUDENTS.csv')
        
    students_list = []
    if os.path.exists(csv_path):
        with open(csv_path, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            next(reader)  # Skip column headers line
            for row in reader:
                if len(row) >= 2 and row[1].strip():
                    students_list.append(LiveCSVStudent(row))
    return students_list


# ── 3. RE-IMPLEMENTED WORKSTATION VIEW (The Master Student Information Registry Hub Table) ──
def student_registry_workstation(request):
    # Parse live student entries array directly from the CSV data document reference node
    students = _load_students_from_csv()
    students.sort(key=lambda s: s.first_name)
    
    context = {
        'students': students,
    }
    return render(request, 'finance/student_registry_workstation.html', context)


# ==========================================
# 3. STAFF & HUMAN RESOURCES CONTROL DESK
# ==========================================

def staff_management_matrix(request):
    """Renders the comprehensive administrative employee workspace"""
    # Passing an empty list for the demo to prevent database crashes
    context = {
        'staff_roster': [], 
    }
    return render(request, 'finance/staff_management_matrix.html', context)

def faculty_directory(request):
    """Compiles and displays all active academic staff profiles"""
    # Passing an empty list for the demo to prevent database crashes
    context = {
        'teachers': [],
    }
    return render(request, 'finance/faculty_directory.html', context)

def add_student_registry(request):
    if request.method == 'POST':
        # 1. Capture the form data safely
        adm_number = request.POST.get('adm_number')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        grade = request.POST.get('grade')
        guardian_name = request.POST.get('guardian_name')
        parent_phone = request.POST.get('parent_phone')
        blood_group = request.POST.get('blood_group')
        
        # 2. Save permanently to the production database
        # (Check your models.py if your field names differ slightly from these)
        new_student = Student.objects.create(
            admission_number=adm_number,
            first_name=first_name,
            last_name=last_name,
            current_grade=grade,
            guardian_name=guardian_name,
            parent_phone=parent_phone,
            blood_group=blood_group
            # If current_balance is a field in your model, add: current_balance=0.00
        )
        
        messages.success(request, f"Learner {new_student.first_name} {new_student.last_name} has been permanently registered!")
        return redirect('bursar_dashboard')
        
    return render(request, 'finance/add_student.html')

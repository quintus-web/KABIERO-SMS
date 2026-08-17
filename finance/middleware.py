# finance/middleware.py
"""
Role-based access control and audit logging middleware.
"""
from django.shortcuts import redirect
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from .models import AuditLog, UserProfile


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def log_audit(user, action, model_name='', object_id='', description='', old_value='', new_value='', request=None):
    ip = get_client_ip(request) if request else ''
    AuditLog.objects.create(
        user=user,
        action=action,
        model_name=model_name,
        object_id=str(object_id),
        description=description,
        old_value=str(old_value) if old_value else '',
        new_value=str(new_value) if new_value else '',
        ip_address=ip,
    )


# URL route names that only ADMIN may access.
ADMIN_ONLY = {
    'executive_kpis',
    'staff_management_matrix',
    'faculty_directory',
    'staff_create',
    'staff_edit',
    'leave_management',
    'grade_promotion',
    'inventory_deck',
    'academic_hub',
    'marks_entry_portal',
    'generate_report_card',
    'post_homework',
    'developer_debug_console',
    'user_role_management',
    'audit_log_viewer',
}

# URL route names that BURSAR or ADMIN may access.
BURSAR_ACCESS = {
    'bursar_dashboard',
    'bulk_balance_import',
    'fee_structure',
    'fee_defaulters_portal',
    'financial_analytics',
    'invoice_list',
    'generate_invoice_pdf',
    'finance_reports',
    'export_report_csv',
    'generate_bulk_invoices',
    'finance_data_entry',
    'lunch_management',
    'expense_register',
    'student_statement',
    'collect_fee_payment',
    'reports',
}

# URL route names that HEADTEACHER, BURSAR, or ADMIN may access.
HEADTEACHER_ACCESS = {
    'student_registry',
    'student_profile',
    'add_new_student_onboarding',
    'attendance_deck',
    'daily_attendance_deck',
    'attendance_history',
    'academic_hub',
    'marks_entry_portal',
    'generate_report_card',
    'academic_analytics',
    'finance_reports',
    'export_report_csv',
    'executive_kpis',
    'inventory_deck',
    'lunch_management',
    'parent_portal_gateway',
    'teacher_sms_broadcast',
    'approval_dashboard',
}


class RoleAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated:
            return None

        url_name = request.resolver_match.url_name if request.resolver_match else None
        if not url_name:
            return None

        profile = getattr(request.user, 'user_profile', None)
        role = profile.role if profile else ('ADMIN' if request.user.is_superuser else 'TEACHER')

        if url_name in ADMIN_ONLY and role not in ('ADMIN',):
            messages.error(request, "Access denied: only System Administrators can open that section.")
            return redirect('executive_kpis')

        if url_name in BURSAR_ACCESS and role not in ('ADMIN', 'BURSAR', 'HEADTEACHER'):
            messages.error(request, "Access denied: only Bursar, Headteachers, and Administrators can open that section.")
            return redirect('executive_kpis')

        if url_name in HEADTEACHER_ACCESS and role not in ('ADMIN', 'BURSAR', 'HEADTEACHER'):
            messages.error(request, "Access denied: you do not have permission to view that section.")
            return redirect('executive_kpis')

        return None


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    try:
        profile = user.user_profile
    except UserProfile.DoesNotExist:
        role = 'ADMIN' if user.is_superuser else 'TEACHER'
        profile = UserProfile.objects.create(user=user, role=role)
    log_audit(user, 'LOGIN', model_name='User', object_id=user.id,
              description=f"User {user.get_full_name() or user.username} logged in", request=request)


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    if user:
        log_audit(user, 'LOGOUT', model_name='User', object_id=user.id,
                  description=f"User {user.get_full_name() or user.username} logged out", request=request)

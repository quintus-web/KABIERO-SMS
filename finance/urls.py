# finance/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from finance import views

urlpatterns = [
    # ── CORE ACCESSIBLE WEB CHANNELS ──
    path('', views.bursar_dashboard),
    
    # ── SECURITY & SESSIONS ACCESS WORKSPACES ──
    path('gateway/login/', views.staff_login_view, name='staff_login'),
    path('gateway/logout/', views.staff_logout_view, name='staff_logout'),
    path('gateway/change-password/', auth_views.PasswordChangeView.as_view(
        template_name='finance/change_password.html',
        success_url='/gateway/password-changed/'
    ), name='password_change'),
    path('gateway/password-changed/', auth_views.PasswordChangeDoneView.as_view(
        template_name='finance/password_changed.html'
    ), name='password_change_done'),
    path('portal/executive-kpis/', views.executive_analytics_kpi_dashboard, name='executive_kpis'),
    
    # ── STUDENT OPERATIONAL DIRECTORY ──
    path('registry/learners/', views.student_registry_workstation, name='student_registry'),
    path('registry/learners/<int:student_id>/folder/', views.single_student_profile_folder, name='student_profile'),
    path('registry/staff-matrix/', views.staff_management_matrix, name='staff_management_matrix'),
    path('registry/faculty/', views.faculty_directory, name='faculty_directory'),
    
    # ── BURSAR ACCOUNTING ENGINE & LEDGERS ──
    path('treasury/data-entry/', views.finance_data_entry, name='finance_data_entry'),
    path('treasury/bulk-balance-import/', views.bulk_balance_import, name='bulk_balance_import'),
    path('treasury/ledger/', views.bursar_dashboard, name='bursar_dashboard'),
    path('treasury/fee-structure/', views.fee_structure, name='fee_structure'),
    path('treasury/lunch/', views.lunch_management, name='lunch_management'),
    path('treasury/expenses/', views.expense_register, name='expense_register'),
    path('treasury/statement/<int:student_id>/', views.student_account_statement, name='student_statement'),
    path('treasury/collect-fees/<int:student_id>/', views.collect_fee_payment, name='collect_fee_payment'),
    path('treasury/defaulters-sms/', views.fee_defaulters_portal, name='fee_defaulters_portal'),
    path('treasury/analytics/', views.financial_analytics, name='financial_analytics'),
    path('treasury/invoices/', views.invoice_list, name='invoice_list'),
    path('treasury/invoice/<int:invoice_id>/pdf/', views.generate_invoice_pdf, name='generate_invoice_pdf'),
    path('treasury/receipt/<int:receipt_id>/pdf/', views.generate_receipt_pdf, name='generate_receipt_pdf'),
    
    # ── FACULTY BROADCASTER ENGINE ──
    path('faculty/class-broadcast/', views.teacher_sms_broadcast, name='teacher_sms_broadcast'),

    # ── ACADEMIC EVALUATION WORKSPACE ──
    path('academic/management-hub/', views.academic_management_hub, name='academic_hub'),
    path('academic/grading-desk/', views.marks_entry_portal, name='marks_entry_portal'),
    path('academic/analytics/', views.academic_analytics_dashboard, name='academic_analytics'),
    path('academic/report-card/<int:student_id>/pdf/', views.generate_report_card_view, name='generate_report_card'),
    path('academic/post-homework/', views.post_homework_assignment, name='post_homework'),
    
    # ── EXTERNAL PARENT GATEWAY SYSTEM ──
    path('parent-portal/', views.parent_portal_gateway, name='parent_portal_gateway'),
    path('parent-portal/logout/', views.parent_logout_view, name='parent_logout'),
    
    # ── ROUTINE ASSET LOGISTICS NODES & ATTENDANCE TRACKERS ──
    path('logistics/attendance-deck/', views.global_attendance_control_deck, name='attendance_deck'),
    path('attendance/daily-deck/', views.daily_attendance_deck, name='daily_attendance_deck'),
    path('attendance/commit-bulk-attendance/', views.commit_bulk_attendance, name='commit_bulk_attendance'),
    path('attendance/history/', views.attendance_history_report, name='attendance_history'),
    path('logistics/inventory/', views.inventory_asset_control_deck, name='inventory_deck'),

    # 🎯 FIXED: Maps the modal onboarding form submission directly to the view function!
    path('add-new-student-onboarding/', views.add_new_student_onboarding, name='add_new_student_onboarding'),

    path('registry/learners/<int:student_id>/edit/', views.edit_student_info, name='edit_student'),
    path('registry/learners/<int:student_id>/delete/', views.delete_student_record, name='delete_student'),
    path('registry/grade-promotion/', views.grade_promotion_dashboard, name='grade_promotion'),
    path('registry/staff/add/', views.staff_create, name='staff_create'),
    path('registry/staff/<int:staff_id>/edit/', views.staff_edit, name='staff_edit'),
    path('registry/staff/leave/', views.leave_management, name='leave_management'),
    
    # ── REPORT HUB & EXPORT ENGINE ──
    path('reports/', views.finance_reports_hub, name='finance_reports'),
    path('reports/export/<str:report_type>/csv/', views.export_report_csv, name='export_report_csv'),
    path('reports/generate-invoices/', views.generate_bulk_invoices, name='generate_bulk_invoices'),
]

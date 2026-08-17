# finance/admin.py
from django.contrib import admin
from .models import Student, Teacher, ClassStream, Subject, AttendanceRecord, DisciplineReport, ExamRecord, FeeInvoice, FeeReceipt, LunchEnrollment, Expense, UserProfile, AuditLog

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone_number', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'user__email')
    ordering = ('user__username',)

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'model_name', 'object_id', 'timestamp', 'ip_address')
    list_filter = ('action', 'timestamp')
    search_fields = ('user__username', 'description', 'model_name', 'object_id')
    readonly_fields = ('user', 'action', 'model_name', 'object_id', 'description', 'old_value', 'new_value', 'ip_address', 'timestamp')
    ordering = ('-timestamp',)

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('admission_number', 'first_name', 'last_name', 'class_stream', 'status', 'is_active', 'current_balance')
    list_filter = ('status', 'class_stream', 'gender', 'is_active')
    search_fields = ('admission_number', 'first_name', 'last_name', 'guardian_name')
    ordering = ('-date_of_admission',)

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('employee_number', 'first_name', 'last_name', 'phone_number', 'specialization')
    search_fields = ('employee_number', 'first_name', 'last_name', 'phone_number')

@admin.register(ClassStream)
class ClassStreamAdmin(admin.ModelAdmin):
    list_display = ('name', 'room_number', 'capacity')
    search_fields = ('name',)

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')
    search_fields = ('code', 'name')

@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ('student', 'date', 'is_present', 'remarks')
    list_filter = ('date', 'is_present')
    search_fields = ('student__first_name', 'student__last_name', 'student__admission_number')

@admin.register(DisciplineReport)
class DisciplineReportAdmin(admin.ModelAdmin):
    list_display = ('student', 'severity', 'date_reported', 'action_taken')
    list_filter = ('severity', 'date_reported')
    search_fields = ('student__first_name', 'student__last_name', 'infraction_details')

@admin.register(ExamRecord)
class ExamRecordAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'term', 'year', 'cat_1', 'cat_2', 'final_exam', 'total_marks')
    list_filter = ('term', 'year', 'subject')
    search_fields = ('student__first_name', 'student__last_name', 'student__admission_number')

@admin.register(FeeInvoice)
class FeeInvoiceAdmin(admin.ModelAdmin):
    list_display = ('student', 'title', 'amount', 'date_issued')
    search_fields = ('student__first_name', 'student__last_name', 'title')

@admin.register(FeeReceipt)
class FeeReceiptAdmin(admin.ModelAdmin):
    list_display = ('student', 'reference_code', 'amount', 'date_paid', 'status')
    list_filter = ('status', 'date_paid')
    search_fields = ('student__first_name', 'student__last_name', 'reference_code')

@admin.register(LunchEnrollment)
class LunchEnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'term', 'year', 'amount', 'is_enrolled')
    list_filter = ('term', 'year', 'is_enrolled')
    search_fields = ('student__admission_number', 'student__first_name', 'student__last_name')

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('expense_date', 'category', 'description', 'amount', 'status', 'payment_method')
    list_filter = ('category', 'status', 'expense_date')
    search_fields = ('description', 'reference_code')

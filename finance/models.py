# finance/models.py
from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

class ClassStream(models.Model):
    name = models.CharField(max_length=50, unique=True)
    room_number = models.CharField(max_length=20, blank=True, null=True)
    capacity = models.IntegerField(default=40)

    def __str__(self):
        return self.name

class FeeStructure(models.Model):
    TERM_CHOICES = [
        ('TERM_1', 'Term 1'),
        ('TERM_2', 'Term 2'),
        ('TERM_3', 'Term 3'),
    ]
    level = models.CharField(max_length=50)
    term = models.CharField(max_length=10, choices=TERM_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    year = models.IntegerField(default=2026)

    class Meta:
        unique_together = ('level', 'term', 'year')
        ordering = ['level', 'term']

    def __str__(self):
        return f"{self.level} - {self.get_term_display()} {self.year}: KES {self.amount:,.2f}"


class LunchEnrollment(models.Model):
    """Optional lunch charge selected separately from the mandatory fee schedule."""
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='lunch_enrollments')
    term = models.CharField(max_length=10, choices=FeeStructure.TERM_CHOICES, default='TERM_1')
    year = models.IntegerField(default=2026)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=3000.00)
    is_enrolled = models.BooleanField(default=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ('student', 'term', 'year')
        ordering = ['student__admission_number']

    def __str__(self):
        return f"Lunch: {self.student} ({self.term} {self.year})"

class Subject(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name} ({self.code})"

class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    employee_number = models.CharField(max_length=30, unique=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone_number = models.CharField(max_length=15)
    specialization = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Mwalimu {self.first_name} {self.last_name}"

class Student(models.Model):
    BLOOD_GROUPS = [('O+', 'O Positive'), ('O-', 'O Negative'), ('A+', 'A Positive'), ('A-', 'A Negative'), ('B+', 'B Positive'), ('AB+', 'AB Positive')]
    STATUS_CHOICES = [('ACTIVE', 'Active Learner'), ('TRANSFERRED', 'Transferred Out'), ('GRADUATED', 'Alumni / Graduated')]
    GENDER_CHOICES = [('M', 'Boy'), ('F', 'Girl')]

    admission_number = models.CharField(max_length=30, unique=True)
    first_name = models.CharField(max_length=50)
    middle_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='M')
    date_of_birth = models.DateField(null=True, blank=True)
    date_of_admission = models.DateField(auto_now_add=True)
    passport_photo_url = models.URLField(max_length=500, blank=True, null=True, default="https://images.unsplash.com/photo-1597545558260-2dc35779abb7?q=80&w=200&auto=format&fit=crop")
    class_stream = models.ForeignKey(ClassStream, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    is_active = models.BooleanField(default=True)

    guardian_name = models.CharField(max_length=100)
    guardian_relation = models.CharField(max_length=50, default="Parent")
    guardian_pin = models.CharField(max_length=128, blank=True, null=True)
    parent_phone = models.CharField(max_length=15)
    parent_email = models.EmailField(blank=True, null=True)
    emergency_contact_name = models.CharField(max_length=100, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=15, blank=True, null=True)

    blood_group = models.CharField(max_length=5, choices=BLOOD_GROUPS, blank=True, null=True)
    known_allergies = models.TextField(blank=True, null=True, default="None Registered")
    medical_conditions = models.TextField(blank=True, null=True, default="None")

    current_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.admission_number})"

class AttendanceRecord(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance')
    date = models.DateField()
    is_present = models.BooleanField(default=True)
    remarks = models.CharField(max_length=150, blank=True, null=True)

    class Meta:
        unique_together = ('student', 'date')

class DisciplineReport(models.Model):
    SEVERITY_LEVELS = [('MINOR', 'Minor Infraction'), ('MEDIUM', 'Requires Guidance'), ('SEVERE', 'Suspension / Board Action')]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='discipline_logs')
    date_reported = models.DateField(auto_now_add=True)
    infraction_details = models.TextField()
    severity = models.CharField(max_length=15, choices=SEVERITY_LEVELS, default='MINOR')
    action_taken = models.CharField(max_length=200, default="Verbal Warning Given")

    def __str__(self):
        return f"{self.severity} - {self.student.last_name}"

class ExamRecord(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    term = models.CharField(max_length=20, default='TERM_1')
    year = models.IntegerField(default=2026)
    cat_1 = models.IntegerField(default=0)
    cat_2 = models.IntegerField(default=0)
    final_exam = models.IntegerField(default=0)

    @property
    def total_marks(self):
        return self.cat_1 + self.cat_2 + self.final_exam

class FeeInvoice(models.Model):
    TERM_CHOICES = [('TERM_1', 'Term 1'), ('TERM_2', 'Term 2'), ('TERM_3', 'Term 3')]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fee_invoices')
    title = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    term = models.CharField(max_length=10, choices=TERM_CHOICES, default='TERM_1')
    year = models.IntegerField(default=2026)
    date_issued = models.DateField(auto_now_add=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Invoice - {self.student.last_name} (KES {self.amount})"

class FeeReceipt(models.Model):
    TERM_CHOICES = [('TERM_1', 'Term 1'), ('TERM_2', 'Term 2'), ('TERM_3', 'Term 3')]
    STATUS_CHOICES = [('COMPLETED', 'Completed'), ('PENDING', 'Pending Verification'), ('FAILED', 'Failed')]
    PAYMENT_CHANNELS = [('MPESA', 'M-Pesa'), ('CASH', 'Cash'), ('BANK', 'Bank Transfer')]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fee_receipts')
    invoice = models.ForeignKey(FeeInvoice, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date_paid = models.DateTimeField(auto_now_add=True)
    date_issued = models.DateTimeField(default=timezone.now)
    reference_code = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=255, default="School Fees Payment")
    payment_channel = models.CharField(max_length=20, choices=PAYMENT_CHANNELS, default='CASH')
    term = models.CharField(max_length=10, choices=TERM_CHOICES, default='TERM_1')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='COMPLETED')

    def __str__(self):
        return f"Receipt {self.reference_code} - KES {self.amount}"


class Expense(models.Model):
    CATEGORY_CHOICES = [
        ('PAYROLL', 'Payroll'),
        ('FOOD', 'Food & Kitchen'),
        ('UTILITIES', 'Utilities'),
        ('SUPPLIES', 'Learning & Office Supplies'),
        ('MAINTENANCE', 'Maintenance & Repairs'),
        ('TRANSPORT', 'Transport'),
        ('OTHER', 'Other'),
    ]
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('APPROVED', 'Approved'),
        ('PAID', 'Paid'),
    ]
    expense_date = models.DateField(default=timezone.now)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=30, default='CASH')
    reference_code = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DRAFT')
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='recorded_expenses')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-expense_date', '-id']

    def __str__(self):
        return f"{self.get_category_display()} - KES {self.amount:,.2f}"
    
class StaffProfile(models.Model):
    ROLE_CHOICES = [
        ('PRINCIPAL', 'School Principal'),
        ('TEACHER', 'Class Teacher'),
        ('ACCOUNTANT', 'Bursar / Accountant'),
        ('SUPPORT', 'Support Staff'),
    ]
    STATUS_CHOICES = [
        ('ACTIVE', 'Active duty'),
        ('ON_LEAVE', 'On Sanctioned Leave'),
        ('SUSPENDED', 'Suspended'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    employee_number = models.CharField(max_length=30, unique=True)
    role_designation = models.CharField(max_length=20, choices=ROLE_CHOICES, default='TEACHER')
    phone_line = models.CharField(max_length=15, default="0700000000")
    specialization = models.CharField(max_length=100, default="Mathematics / Physics")
    base_salary_kes = models.DecimalField(max_digits=12, decimal_places=2, default=45000.00)
    current_status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='ACTIVE')
    performance_score = models.IntegerField(default=85)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.employee_number})"

class LeaveApplication(models.Model):
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name='leaves')
    leave_reason = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    is_approved = models.BooleanField(default=False)

class TimetableAllocation(models.Model):
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name='classes_taught')
    stream = models.ForeignKey(ClassStream, on_delete=models.CASCADE)
    subject_title = models.CharField(max_length=50)
    weekday = models.CharField(max_length=15, default="Monday")
    time_slot = models.CharField(max_length=20, default="08:00 AM - 08:40 AM")

class StudentAttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ('PRESENT', 'Present'),
        ('ABSENT', 'Absent'),
        ('LATE', 'Late with Excuse'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_history')
    date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PRESENT')
    is_present = models.BooleanField(default=True)
    verification_method = models.CharField(max_length=30, default='BIOMETRIC_SCAN')
    logged_at = models.DateTimeField(auto_now_add=True)
    remarks = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        unique_together = ('student', 'date')

class TeacherAttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ('PRESENT', 'Present'),
        ('ABSENT', 'Absent'),
        ('ON_LEAVE', 'Sanctioned Leave'),
    ]
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name='staff_attendance')
    date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PRESENT')
    time_in = models.TimeField(null=True, blank=True)
    logged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('staff', 'date')

class HomeworkAssignment(models.Model):
    stream = models.ForeignKey(ClassStream, on_delete=models.CASCADE, related_name='assignments')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    title = models.CharField(max_length=150)
    task_instructions = models.TextField()
    date_given = models.DateField(default=timezone.now)
    submission_deadline = models.DateField()

    def __str__(self):
        return f"{self.subject.name} - {self.title}"

class SchoolAnnouncement(models.Model):
    NOTICE_TARGETS = [
        ('ALL_PARENTS', 'All Parents'),
        ('ALL_STUDENTS', 'All Students'),
        ('FORM_1', 'Form 1 Stream Blocks Only'),
        ('FORM_2', 'Form 2 Stream Blocks Only'),
    ]
    title = models.CharField(max_length=200)
    announcement_body = models.TextField()
    target_audience = models.CharField(max_length=20, choices=NOTICE_TARGETS, default='ALL_PARENTS')
    date_published = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.title
    
class SchoolAsset(models.Model):
    CATEGORY_CHOICES = [
        ('TEXTBOOKS', 'Textbook Inventory'),
        ('LAB_EQUIP', 'Computer & Lab Equipment'),
        ('FURNITURE', 'School Furniture Property'),
        ('STORES', 'General Store Supplies'),
    ]
    ASSET_STATUS = [
        ('OPERATIONAL', 'Operational / Active'),
        ('UNDER_REPAIR', 'Under Maintenance'),
        ('DECOMMISSIONED', 'Decommissioned / Written Off'),
    ]
    
    name = models.CharField(max_length=150)
    serial_or_isbn = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    total_quantity = models.PositiveIntegerField(default=1)
    available_quantity = models.PositiveIntegerField(default=1)
    assigned_location = models.CharField(max_length=100, help_text="e.g., Science Lab B, Form 2 Alpha Room")
    status = models.CharField(max_length=20, choices=ASSET_STATUS, default='OPERATIONAL')
    last_audited_date = models.DateField(default=timezone.now)

    def __str__(self):
        return f"[{self.get_category_display()}] {self.name}"

class AssetMaintenanceLog(models.Model):
    asset = models.ForeignKey(SchoolAsset, on_delete=models.CASCADE, related_name='maintenance_history')
    issue_reported = models.TextField()
    action_taken = models.TextField(blank=True, null=True)
    cost_incurred_kes = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    date_logged = models.DateField(default=timezone.now)
    is_resolved = models.BooleanField(default=False)

    def __str__(self):
        return f"Fix Log: {self.asset.name} on {self.date_logged}"
    
class LessonPlan(models.Model):
    teacher = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, limit_choices_to={'role_designation': 'TEACHER'})
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    stream = models.ForeignKey(ClassStream, on_delete=models.CASCADE)
    topic = models.CharField(max_length=150)
    objectives = models.TextField(help_text="What will learners achieve by the end of this lesson?")
    week_number = models.PositiveIntegerField(default=1)
    date_planned = models.DateField()
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"Week {self.week_number} - {self.subject.name}: {self.topic}"

class LearningMaterial(models.Model):
    MATERIAL_TYPES = [
        ('NOTES', 'Revision Notes'),
        ('PAST_PAPER', 'Past Examination Paper'),
        ('SYLLABUS', 'Curriculum Syllabus Guide'),
    ]
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    title = models.CharField(max_length=150)
    material_type = models.CharField(max_length=15, choices=MATERIAL_TYPES, default='NOTES')
    resource_url = models.URLField(help_text="Link to digital storage hosted notes or files (e.g., Google Drive/OneDrive)")
    date_uploaded = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"[{self.get_material_type_display()}] {self.title}"

class TimetableSlot(models.Model):
    DAYS_OF_WEEK = [
        ('MON', 'Monday'),
        ('TUE', 'Tuesday'),
        ('WED', 'Wednesday'),
        ('THU', 'Thursday'),
        ('FRI', 'Friday'),
    ]
    stream = models.ForeignKey(ClassStream, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, limit_choices_to={'role_designation': 'TEACHER'})
    day = models.CharField(max_length=3, choices=DAYS_OF_WEEK)
    time_start = models.TimeField()
    time_end = models.TimeField()

    def __str__(self):
        return f"{self.get_day_display()} | {self.time_start.strftime('%H:%M')} - {self.time_end.strftime('%H:%M')} ({self.subject.code})"


class SchoolHoliday(models.Model):
    name = models.CharField(max_length=150)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True, help_text="Leave blank for a single-day holiday")
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['start_date']

    def __str__(self):
        if self.end_date and self.end_date != self.start_date:
            return f"{self.name} ({self.start_date} – {self.end_date})"
        return f"{self.name} ({self.start_date})"

    @property
    def covers(self):
        return self.end_date or self.start_date


class UserProfile(models.Model):
    SYSTEM_ROLES = [
        ('ADMIN', 'System Administrator'),
        ('BURSAR', 'Bursar / Finance Controller'),
        ('HEADTEACHER', 'Headteacher'),
        ('TEACHER', 'Teacher'),
        ('SUPPORT', 'Support Staff'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='user_profile')
    role = models.CharField(max_length=20, choices=SYSTEM_ROLES, default='TEACHER')
    phone_number = models.CharField(max_length=15, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['user__username']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"

    @property
    def is_admin(self):
        return self.role == 'ADMIN'

    @property
    def is_bursar(self):
        return self.role == 'BURSAR'

    @property
    def is_headteacher(self):
        return self.role == 'HEADTEACHER'

    @property
    def is_teacher(self):
        return self.role == 'TEACHER'

    @property
    def is_support(self):
        return self.role == 'SUPPORT'


class AuditLog(models.Model):
    ACTION_TYPES = [
        ('CREATE', 'Created'),
        ('UPDATE', 'Updated'),
        ('DELETE', 'Deleted'),
        ('APPROVE', 'Approved'),
        ('REJECT', 'Rejected'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('PAYMENT', 'Payment Recorded'),
        ('BALANCE', 'Balance Changed'),
        ('ROLE_CHANGE', 'Role Changed'),
        ('IMPORT', 'Data Imported'),
        ('OTHER', 'Other'),
    ]
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_TYPES)
    model_name = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['action', 'timestamp']),
        ]

    def __str__(self):
        user_str = self.user.get_full_name() if self.user else 'System'
        return f"{user_str} - {self.get_action_display()} {self.model_name} ({self.timestamp.strftime('%Y-%m-%d %H:%M')})"


class ApprovalRequest(models.Model):
    PENDING = 'PENDING'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'

    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
    ]

    TYPE_EXPENSE = 'EXPENSE'
    TYPE_STUDENT_DELETION = 'STUDENT_DELETION'
    TYPE_GRADE_PROMOTION = 'GRADE_PROMOTION'
    TYPE_BALANCE_ADJUSTMENT = 'BALANCE_ADJUSTMENT'
    TYPE_INVOICE_ADJUSTMENT = 'INVOICE_ADJUSTMENT'

    TYPE_CHOICES = [
        (TYPE_EXPENSE, 'Expense'),
        (TYPE_STUDENT_DELETION, 'Student Record Deletion'),
        (TYPE_GRADE_PROMOTION, 'Grade Promotion'),
        (TYPE_BALANCE_ADJUSTMENT, 'Balance Adjustment'),
        (TYPE_INVOICE_ADJUSTMENT, 'Invoice Adjustment'),
    ]

    approval_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='approval_requests_made')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approval_requests_reviewed')

    reason = models.TextField(blank=True, help_text="Reason for the request")
    rejection_reason = models.TextField(blank=True, help_text="Reason for rejection")

    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'approval_type', 'created_at']),
            models.Index(fields=['requested_by', 'status']),
        ]

    def __str__(self):
        return f"{self.get_approval_type_display()} - {self.get_status_display()} (by {self.requested_by.get_full_name() or self.requested_by.username})"

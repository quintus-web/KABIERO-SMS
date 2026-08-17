from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from decimal import Decimal
from datetime import date

from finance.models import (
    Student, ClassStream, Subject, Expense, ApprovalRequest,
    UserProfile, StaffProfile
)


class ApprovalWorkflowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser('admin', 'admin@test.com', 'adminpass')
        self.bursar_user = User.objects.create_user('bursar', 'bursar@test.com', 'bursarpass')
        self.headteacher_user = User.objects.create_user('head', 'head@test.com', 'headpass')

        UserProfile.objects.create(user=self.admin_user, role='ADMIN')
        UserProfile.objects.create(user=self.bursar_user, role='BURSAR')
        UserProfile.objects.create(user=self.headteacher_user, role='HEADTEACHER')

        self.stream = ClassStream.objects.create(name='Form 1', room_number='R1', capacity=40)
        self.student = Student.objects.create(
            admission_number='ADM001',
            first_name='John',
            last_name='Doe',
            gender='M',
            class_stream=self.stream,
            guardian_name='Parent',
            parent_phone='0712345678',
            current_balance=Decimal('0.00')
        )

    def test_bursar_creates_expense_as_draft(self):
        self.client.login(username='bursar', password='bursarpass')
        response = self.client.post(reverse('expense_register'), {
            'expense_date': '2026-08-17',
            'category': 'FOOD',
            'description': 'Test expense',
            'amount': '1000.00',
            'payment_method': 'CASH',
            'reference_code': 'REF001',
            'status': 'PAID',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        expense = Expense.objects.first()
        self.assertEqual(expense.status, 'DRAFT')
        approval = ApprovalRequest.objects.first()
        self.assertEqual(approval.approval_type, 'EXPENSE')
        self.assertEqual(approval.status, 'PENDING')
        self.assertEqual(approval.requested_by, self.bursar_user)

    def test_admin_auto_approves_expense(self):
        self.client.login(username='admin', password='adminpass')
        response = self.client.post(reverse('expense_register'), {
            'expense_date': '2026-08-17',
            'category': 'FOOD',
            'description': 'Admin expense',
            'amount': '2000.00',
            'payment_method': 'CASH',
            'reference_code': 'REF002',
            'status': 'PAID',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        expense = Expense.objects.first()
        self.assertEqual(expense.status, 'APPROVED')
        self.assertEqual(ApprovalRequest.objects.count(), 0)

    def test_headteacher_can_approve_expense(self):
        self.client.login(username='bursar', password='bursarpass')
        self.client.post(reverse('expense_register'), {
            'expense_date': '2026-08-17',
            'category': 'FOOD',
            'description': 'Pending expense',
            'amount': '1500.00',
            'payment_method': 'CASH',
            'reference_code': 'REF003',
            'status': 'PAID',
        }, follow=True)
        approval = ApprovalRequest.objects.first()
        self.assertIsNotNone(approval)

        self.client.login(username='head', password='headpass')
        response = self.client.post(reverse('approve_request', args=[approval.id]), follow=True)
        self.assertEqual(response.status_code, 200)
        approval.refresh_from_db()
        self.assertEqual(approval.status, 'APPROVED')
        approval.content_object.refresh_from_db()
        self.assertEqual(approval.content_object.status, 'APPROVED')

    def test_headteacher_can_reject_expense(self):
        self.client.login(username='bursar', password='bursarpass')
        self.client.post(reverse('expense_register'), {
            'expense_date': '2026-08-17',
            'category': 'FOOD',
            'description': 'Bad expense',
            'amount': '500.00',
            'payment_method': 'CASH',
            'reference_code': 'REF004',
            'status': 'PAID',
        }, follow=True)
        approval = ApprovalRequest.objects.first()
        self.assertIsNotNone(approval)

        self.client.login(username='head', password='headpass')
        response = self.client.post(reverse('reject_request', args=[approval.id]), {
            'rejection_reason': 'Not approved'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        approval.refresh_from_db()
        self.assertEqual(approval.status, 'REJECTED')
        self.assertEqual(approval.rejection_reason, 'Not approved')
        approval.content_object.refresh_from_db()
        self.assertEqual(approval.content_object.status, 'REJECTED')

from django import forms
from .models import FeeReceipt, Student, Expense

class ReceiptEntryForm(forms.ModelForm):
    student_admission = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Student Admission Number'})
    )

    class Meta:
        model = FeeReceipt
        fields = ['reference_code', 'amount', 'payment_channel']
        widgets = {
            'reference_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. QRE789XYZ'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'payment_channel': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean_student_admission(self):
        adm_no = self.cleaned_data.get('student_admission', '').strip()
        if not Student.objects.filter(admission_number=adm_no, is_active=True).exists():
            raise forms.ValidationError("No active student found with this admission number.")
        return adm_no


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['expense_date', 'category', 'description', 'amount', 'payment_method', 'reference_code', 'status']
        widgets = {
            'expense_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'What was purchased or paid for?'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'min': '0.01', 'step': '0.01'}),
            'payment_method': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Cash, M-Pesa, bank…'}),
            'reference_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Receipt / payment reference'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

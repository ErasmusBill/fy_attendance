from django import forms
from apps.members.models import Members, Department


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-900 placeholder-slate-400 focus:bg-white focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition',
                'placeholder': 'e.g. Choir, Ushering, Media, Youth Fellowship'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-900 placeholder-slate-400 focus:bg-white focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition',
                'rows': 3,
                'placeholder': 'Brief description of this ministry/department...'
            }),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        qs = Department.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A department with this name already exists.")
        return name


class MemberForm(forms.ModelForm):
    class Meta:
        model = Members
        fields = ['department', 'name', 'email', 'phone_number', 'date_of_birth', 'address']
        widgets = {
            'department': forms.Select(attrs={
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-900 focus:bg-white focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition'
            }),
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-900 placeholder-slate-400 focus:bg-white focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition',
                'placeholder': 'e.g. Grace Mensah'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-900 placeholder-slate-400 focus:bg-white focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition',
                'placeholder': 'grace.mensah@example.com'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-900 placeholder-slate-400 focus:bg-white focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition',
                'placeholder': '+1 234 567 8900'
            }),
            'date_of_birth': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-900 focus:bg-white focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition'
            }),
            'address': forms.Textarea(attrs={
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-900 placeholder-slate-400 focus:bg-white focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition',
                'rows': 3,
                'placeholder': 'Residential address / Location'
            }),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        qs = Members.objects.filter(email=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A church member with this email address already exists.")
        return email

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number', '').strip()
        qs = Members.objects.filter(phone_number=phone_number)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A church member with this phone number already exists.")
        return phone_number

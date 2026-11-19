from django import forms
from apps.members.models import Location, Department, Members
from .models import AttendanceSession


class AttendanceSessionForm(forms.ModelForm):
    class Meta:
        model = AttendanceSession
        fields = ['title', 'location', 'date', 'start_time', 'end_time', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-900 focus:bg-white focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition',
                'placeholder': 'e.g. Sunday Celebration Service'
            }),
            'location': forms.Select(attrs={
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-900 focus:bg-white focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition'
            }),
            'date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-900 focus:bg-white focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition'
            }),
            'start_time': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-900 focus:bg-white focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition'
            }),
            'end_time': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-900 focus:bg-white focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 bg-white border-slate-300 rounded focus:ring-blue-500'
            }),
        }


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ['name', 'latitude', 'longitude', 'radius', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-900 focus:bg-white focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition',
                'placeholder': 'e.g. Main Sanctuary Auditorium'
            }),
            'latitude': forms.NumberInput(attrs={
                'step': '0.000001',
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-900 focus:bg-white focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition',
                'placeholder': 'e.g. 5.603717'
            }),
            'longitude': forms.NumberInput(attrs={
                'step': '0.000001',
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-900 focus:bg-white focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition',
                'placeholder': 'e.g. -0.186964'
            }),
            'radius': forms.NumberInput(attrs={
                'step': '1',
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-900 focus:bg-white focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition',
                'placeholder': 'Radius in meters (e.g. 150)'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-900 focus:bg-white focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition',
                'rows': 2,
                'placeholder': 'Description or address'
            }),
        }

    def clean_radius(self):
        radius = self.cleaned_data.get('radius')
        if radius is not None and radius < 20:
            raise forms.ValidationError(
                f"Radius of {radius}m is too small. Smartphone GPS has a natural drift of 10–25m indoors. Please specify at least 20 meters (recommended: 100m – 200m for church sanctuary campuses)."
            )
        return radius


class CheckInForm(forms.Form):
    member_id = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 bg-white border-2 border-slate-300 rounded-xl text-base text-slate-900 font-semibold tracking-wider placeholder-slate-400 focus:outline-none focus:border-blue-600 focus:ring-4 focus:ring-blue-100 transition text-center uppercase',
            'placeholder': 'ENTER MEMBER ID (e.g. FY-0011)',
            'autocomplete': 'off',
            'autofocus': 'true'
        })
    )
    latitude = forms.FloatField(
        required=True,
        widget=forms.HiddenInput(attrs={'id': 'id_latitude'})
    )
    longitude = forms.FloatField(
        required=True,
        widget=forms.HiddenInput(attrs={'id': 'id_longitude'})
    )
    device_info = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'id_device_info'})
    )


class QuickMemberCheckInForm(forms.Form):
    """
    Used by Ushers to quickly register a new congregant at the door
    who is not yet in the portal and mark them present immediately.
    """
    name = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-900 focus:bg-white focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition',
            'placeholder': 'Full Name (e.g. Kwame Mensah)'
        })
    )
    phone_number = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-900 focus:bg-white focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition',
            'placeholder': '+233 24 123 4567'
        })
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=True,
        widget=forms.Select(attrs={
            'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-900 focus:bg-white focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition'
        })
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-900 focus:bg-white focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition',
            'placeholder': 'Optional email address'
        })
    )
    date_of_birth = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-900 focus:bg-white focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition'
        })
    )
    address = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-900 focus:bg-white focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition',
            'placeholder': 'Optional residential address / area'
        })
    )

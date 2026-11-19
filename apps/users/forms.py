from django import forms
from apps.users.models import User, UserProfile, Roles

STAFF_ROLE_CHOICES = [
    (Roles.ADMIN, 'Church Administrator'),
    (Roles.PASTOR, 'Pastor / Minister'),
    (Roles.USHER, 'Usher / Protocol Team'),
    (Roles.STAFF, 'Church Staff'),
]

UPDATE_ROLE_CHOICES = STAFF_ROLE_CHOICES + [
    (Roles.USER, 'General Staff (Legacy)'),
]


class AdminCreateUserForm(forms.Form):
    first_name = forms.CharField(required=True, max_length=255)
    last_name = forms.CharField(required=True, max_length=255)
    email = forms.EmailField(required=True)
    phone_number = forms.CharField(required=True, max_length=255)
    password = forms.CharField(required=True, widget=forms.PasswordInput)
    date_of_birth = forms.DateField(required=True, widget=forms.DateInput(attrs={'type': 'date'}))
    role = forms.ChoiceField(choices=STAFF_ROLE_CHOICES, required=True)
    location = forms.CharField(required=True, max_length=255)
    avatar = forms.ImageField(required=False)

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if len(password) < 8:
            raise forms.ValidationError("Password must be at least 8 characters.")
        return password

    def save(self):
        cleaned_data = self.cleaned_data
        user = User.objects.create_user(
            email=cleaned_data['email'],
            password=cleaned_data['password'],
            first_name=cleaned_data['first_name'],
            last_name=cleaned_data['last_name'],
            phone_number=cleaned_data['phone_number'],
            role=cleaned_data['role']
        )

        profile = UserProfile.objects.create(
            user=user,
            date_of_birth=cleaned_data['date_of_birth'],
            location=cleaned_data['location'],
            avatar=cleaned_data.get('avatar')
        )
        return user


class AdminUpdateUserForm(forms.Form):
    first_name = forms.CharField(required=True, max_length=255)
    last_name = forms.CharField(required=True, max_length=255)
    email = forms.EmailField(required=True)
    phone_number = forms.CharField(required=False, max_length=255)
    date_of_birth = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    role = forms.ChoiceField(choices=UPDATE_ROLE_CHOICES, required=True)
    location = forms.CharField(required=False, max_length=255)
    avatar = forms.ImageField(required=False)

    def __init__(self, *args, user_instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_instance = user_instance

    def clean_email(self):
        email = self.cleaned_data.get('email')
        qs = User.objects.filter(email=email)
        if self.user_instance:
            qs = qs.exclude(pk=self.user_instance.pk)
        if qs.exists():
            raise forms.ValidationError("Another user with this email already exists.")
        return email

    def save(self, user):
        cleaned = self.cleaned_data
        user.first_name = cleaned['first_name']
        user.last_name = cleaned['last_name']
        user.email = cleaned['email']
        user.phone_number = cleaned.get('phone_number') or ''
        user.role = cleaned['role']
        user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user, defaults={
            'date_of_birth': cleaned.get('date_of_birth') or '2000-01-01',
            'location': cleaned.get('location') or ''
        })
        if cleaned.get('date_of_birth'):
            profile.date_of_birth = cleaned['date_of_birth']
        if cleaned.get('location') is not None:
            profile.location = cleaned['location']
        if cleaned.get('avatar'):
            profile.avatar = cleaned['avatar']
        profile.save()
        return user


class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(required=True, widget=forms.PasswordInput)
    new_password1 = forms.CharField(required=True, widget=forms.PasswordInput)
    new_password2 = forms.CharField(required=True, widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        new_password1 = cleaned_data.get('new_password1')
        new_password2 = cleaned_data.get('new_password2')

        if new_password1 and new_password2 and new_password1 != new_password2:
            raise forms.ValidationError("The two new password fields didn't match.")

        if new_password1 and len(new_password1) < 8:
            raise forms.ValidationError("Password must be at least 8 characters long.")

        return cleaned_data


class PasswordResetForm(forms.Form):
    email = forms.EmailField(required=True)

    def clean_email(self):
        email = self.cleaned_data.get('email')
        email = User.objects.normalize_email(email)

        if not User.objects.filter(email=email, is_active=True).exists():
            raise forms.ValidationError("No active user account was found with this email address.")

        return email

    def save(self, request):
        email = self.cleaned_data['email']
        associated_users = User.objects.filter(email=email, is_active=True)

        for user in associated_users:
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            context = {
                'email': user.email,
                'domain': request.get_host(),
                'site_name': 'Church Attendance System',
                'uid': uid,
                'user': user,
                'token': token,
                'protocol': 'https' if request.is_secure() else 'http',
            }

            subject = "Password Reset Requested - Church Attendance System"
            email_body = render_to_string("registration/password_reset_email.html", context)

            send_mail(
                subject,
                email_body,
                getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@churchattendance.org'),
                [user.email],
                fail_silently=True,
            )

from django import forms
from django.contrib.auth.models import User

from .models import Role


class UserCreateForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput, min_length=6)
    role = forms.ChoiceField(choices=Role.choices)
    position = forms.CharField(max_length=80, required=False)
    phone = forms.CharField(max_length=20, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "inp")

    def clean_username(self):
        u = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=u).exists():
            raise forms.ValidationError("Username already taken.")
        return u

    def save(self):
        d = self.cleaned_data
        user = User.objects.create_user(username=d["username"], password=d["password"])
        user.is_staff = (d["role"] == Role.ADMIN)
        user.is_superuser = (d["role"] == Role.ADMIN)
        user.save()
        p = user.profile  # auto-created by signal
        p.role = d["role"]; p.position = d["position"]; p.phone = d["phone"]
        p.save()
        return user


class UserEditForm(forms.Form):
    role = forms.ChoiceField(choices=Role.choices)
    position = forms.CharField(max_length=80, required=False)
    phone = forms.CharField(max_length=20, required=False)
    is_active = forms.BooleanField(required=False, initial=True)
    new_password = forms.CharField(widget=forms.PasswordInput, required=False,
                                   help_text="Leave blank to keep current.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, f in self.fields.items():
            f.widget.attrs.setdefault("class", "h-4 w-4" if name == "is_active" else "inp")

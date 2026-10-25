from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from audit.models import AuditEvent
from audit.services import record_access_denied, write_ledger_event


User = get_user_model()


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.role = User.Role.VIEWER
        if commit:
            user.save()
        return user


class VaultSignInView(auth_views.LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True
    next_page = reverse_lazy("dashboard")

    def form_valid(self, form):
        response = super().form_valid(form)
        write_ledger_event(
            actor=self.request.user,
            action=AuditEvent.Action.LOGIN,
            ip_address=self.request.META.get("REMOTE_ADDR"),
            details={"operation": "login"},
        )
        return response

    def form_invalid(self, form):
        record_access_denied(
            actor=None,
            operation="login",
            ip_address=self.request.META.get("REMOTE_ADDR"),
        )
        return super().form_invalid(form)


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = SignUpForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("login")

    return render(request, "accounts/signup.html", {"form": form})

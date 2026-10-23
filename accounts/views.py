from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy

from audit.models import AuditEvent
from audit.services import record_access_denied, write_ledger_event


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

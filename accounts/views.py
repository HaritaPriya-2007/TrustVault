
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy


class TrustVaultLoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True
    next_page = reverse_lazy("dashboard")

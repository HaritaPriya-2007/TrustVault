
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import TrustVaultLoginView

urlpatterns = [
    path("login/", TrustVaultLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
]

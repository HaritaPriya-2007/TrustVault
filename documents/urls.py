from django.urls import path

from . import views

urlpatterns = [
    path("", views.my_documents, name="my_documents"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("upload/", views.upload_document, name="upload_document"),
    path("<uuid:document_id>/", views.inspect_document, name="inspect_document"),
    path(
        "<uuid:document_id>/download/",
        views.download_document,
        name="download_document",
    ),
    path("<uuid:document_id>/edit/", views.edit_document, name="edit_document"),
    path("<uuid:document_id>/share/", views.share_document, name="share_document"),
    path(
        "<uuid:document_id>/share/<int:grant_id>/withdraw/",
        views.revoke_document_access,
        name="revoke_document_access",
    ),
    path(
        "<uuid:document_id>/retire/",
        views.retire_document,
        name="retire_document",
    ),
]

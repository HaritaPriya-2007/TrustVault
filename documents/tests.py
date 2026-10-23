
from audit.models import AuditEvent
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Document, DocumentGrant
from .permissions import get_authorized_document

User = get_user_model()


@override_settings(MEDIA_ROOT="/tmp/trustvault-test-media")
class DocumentPermissionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner",
            password="test-password-1",
            role=User.Role.OWNER,
        )
        self.viewer = User.objects.create_user(
            username="viewer",
            password="test-password-2",
            role=User.Role.VIEWER,
        )
        self.other_user = User.objects.create_user(
            username="other",
            password="test-password-3",
            role=User.Role.VIEWER,
        )

        self.document = Document.objects.create(
            title="Confidential contract",
            category="Contracts",
            owner=self.owner,
            file=SimpleUploadedFile(
                "contract.txt",
                b"confidential test content",
                content_type="text/plain",
            ),
            original_filename="contract.txt",
            content_type="text/plain",
            size_bytes=26,
        )

    def test_owner_can_read_document(self):
        result = get_authorized_document(
            self.owner, self.document.pk, "read"
        )
        self.assertEqual(result.pk, self.document.pk)

    def test_ungranted_user_cannot_read_document(self):
        with self.assertRaises(Exception) as ctx:
            get_authorized_document(
                self.other_user, self.document.pk, "read"
            )

        self.assertEqual(ctx.exception.__class__.__name__, "Http404")

    def test_read_grant_allows_read_but_not_edit(self):
        DocumentGrant.objects.create(
            document=self.document,
            user=self.viewer,
            granted_by=self.owner,
            access_level=DocumentGrant.AccessLevel.READ,
        )

        self.assertEqual(
            get_authorized_document(
                self.viewer, self.document.pk, "read"
            ).pk,
            self.document.pk,
        )

        with self.assertRaises(PermissionDenied):
            get_authorized_document(
                self.viewer, self.document.pk, "edit"
            )

    def test_revoked_grant_no_longer_allows_read(self):
        grant = DocumentGrant.objects.create(
            document=self.document,
            user=self.viewer,
            granted_by=self.owner,
            access_level=DocumentGrant.AccessLevel.READ,
        )
        grant.revoked_at = timezone.now()
        grant.save(update_fields=["revoked_at"])

        with self.assertRaises(Exception) as ctx:
            get_authorized_document(
                self.viewer, self.document.pk, "read"
            )

        self.assertEqual(ctx.exception.__class__.__name__, "Http404")

    def test_editor_cannot_share_or_delete(self):
        DocumentGrant.objects.create(
            document=self.document,
            user=self.viewer,
            granted_by=self.owner,
            access_level=DocumentGrant.AccessLevel.EDIT,
        )

        for action in ("share", "delete"):
            with self.assertRaises(PermissionDenied):
                get_authorized_document(
                    self.viewer, self.document.pk, action
                )

    def test_unauthorized_download_is_denied(self):
        self.client.force_login(self.other_user)

        response = self.client.get(
            reverse(
                "download_document",
                kwargs={"document_id": self.document.pk},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_download_redirects_to_login(self):
        response = self.client.get(
            reverse(
                "download_document",
                kwargs={"document_id": self.document.pk},
            )
        )

        self.assertEqual(response.status_code, 302)

    def test_granted_viewer_can_download(self):
        DocumentGrant.objects.create(
            document=self.document,
            user=self.viewer,
            granted_by=self.owner,
            access_level=DocumentGrant.AccessLevel.READ,
        )
        self.client.force_login(self.viewer)

        response = self.client.get(
            reverse(
                "download_document",
                kwargs={"document_id": self.document.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            b"".join(response.streaming_content),
            b"confidential test content",
        )
        response.close()

    def test_revoked_viewer_cannot_download(self):
        grant = DocumentGrant.objects.create(
            document=self.document,
            user=self.viewer,
            granted_by=self.owner,
            access_level=DocumentGrant.AccessLevel.READ,
        )
        self.client.force_login(self.viewer)

        url = reverse(
            "download_document",
            kwargs={"document_id": self.document.pk},
        )

        first_response = self.client.get(url)
        self.assertEqual(first_response.status_code, 200)
        first_response.close()

        grant.revoked_at = timezone.now()
        grant.save(update_fields=["revoked_at"])

        second_response = self.client.get(url)
        self.assertEqual(second_response.status_code, 404)

    def test_unauthorized_download_is_audited(self):
        self.client.force_login(self.other_user)

        url = reverse(
            "download_document",
            kwargs={"document_id": self.document.pk},
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            AuditEvent.objects.filter(
                actor=self.other_user,
                action=AuditEvent.Action.ACCESS_DENIED,
                success=False,
                details__operation="download",
            ).exists()
        )

    def test_successful_download_is_audited(self):
        DocumentGrant.objects.create(
            document=self.document,
            user=self.viewer,
            granted_by=self.owner,
            access_level=DocumentGrant.AccessLevel.READ,
        )
        self.client.force_login(self.viewer)

        url = reverse(
            "download_document",
            kwargs={"document_id": self.document.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response.close()

        self.assertTrue(
            AuditEvent.objects.filter(
                actor=self.viewer,
                document=self.document,
                action=AuditEvent.Action.DOWNLOAD,
                success=True,
            ).exists()
        )


@override_settings(MEDIA_ROOT="/tmp/trustvault-test-media")
class DocumentSharingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="share_owner",
            password="test-password-1",
            role=User.Role.OWNER,
        )
        self.viewer = User.objects.create_user(
            username="share_viewer",
            password="test-password-2",
            role=User.Role.VIEWER,
        )
        self.other_user = User.objects.create_user(
            username="share_other",
            password="test-password-3",
            role=User.Role.VIEWER,
        )

        self.document = Document.objects.create(
            title="Shared contract",
            category="Contracts",
            owner=self.owner,
            file=SimpleUploadedFile(
                "shared-contract.txt",
                b"sharing test content",
                content_type="text/plain",
            ),
            original_filename="shared-contract.txt",
            content_type="text/plain",
            size_bytes=len(b"sharing test content"),
        )

        self.share_url = reverse(
            "share_document",
            kwargs={"document_id": self.document.pk},
        )

    def test_owner_can_grant_read_access(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.share_url,
            {
                "username": self.viewer.username,
                "access_level": DocumentGrant.AccessLevel.READ,
            },
        )

        self.assertEqual(response.status_code, 302)
        grant = DocumentGrant.objects.get(
            document=self.document,
            user=self.viewer,
        )
        self.assertEqual(
            grant.access_level, DocumentGrant.AccessLevel.READ
        )
        self.assertIsNone(grant.revoked_at)

    def test_owner_can_grant_edit_access(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.share_url,
            {
                "username": self.viewer.username,
                "access_level": DocumentGrant.AccessLevel.EDIT,
            },
        )

        self.assertEqual(response.status_code, 302)
        grant = DocumentGrant.objects.get(
            document=self.document,
            user=self.viewer,
        )
        self.assertEqual(
            grant.access_level, DocumentGrant.AccessLevel.EDIT
        )

    def test_grant_action_is_audited(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.share_url,
            {
                "username": self.viewer.username,
                "access_level": DocumentGrant.AccessLevel.READ,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            AuditEvent.objects.filter(
                actor=self.owner,
                document=self.document,
                action=AuditEvent.Action.GRANT,
                success=True,
                details__recipient=self.viewer.username,
            ).exists()
        )

    def test_owner_can_revoke_access(self):
        grant = DocumentGrant.objects.create(
            document=self.document,
            user=self.viewer,
            granted_by=self.owner,
            access_level=DocumentGrant.AccessLevel.READ,
        )
        self.client.force_login(self.owner)

        revoke_url = reverse(
            "revoke_document_access",
            kwargs={
                "document_id": self.document.pk,
                "grant_id": grant.pk,
            },
        )
        response = self.client.post(revoke_url)

        self.assertEqual(response.status_code, 302)
        grant.refresh_from_db()
        self.assertIsNotNone(grant.revoked_at)

    def test_revoke_action_is_audited(self):
        grant = DocumentGrant.objects.create(
            document=self.document,
            user=self.viewer,
            granted_by=self.owner,
            access_level=DocumentGrant.AccessLevel.READ,
        )
        self.client.force_login(self.owner)

        revoke_url = reverse(
            "revoke_document_access",
            kwargs={
                "document_id": self.document.pk,
                "grant_id": grant.pk,
            },
        )
        response = self.client.post(revoke_url)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            AuditEvent.objects.filter(
                actor=self.owner,
                document=self.document,
                action=AuditEvent.Action.REVOKE,
                success=True,
                details__recipient=self.viewer.username,
            ).exists()
        )

    def test_viewer_cannot_share_document(self):
        DocumentGrant.objects.create(
            document=self.document,
            user=self.viewer,
            granted_by=self.owner,
            access_level=DocumentGrant.AccessLevel.EDIT,
        )
        self.client.force_login(self.viewer)

        response = self.client.post(
            self.share_url,
            {
                "username": self.other_user.username,
                "access_level": DocumentGrant.AccessLevel.READ,
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            DocumentGrant.objects.filter(
                document=self.document,
                user=self.other_user,
            ).exists()
        )

    def test_viewer_cannot_revoke_another_users_access(self):
        grant = DocumentGrant.objects.create(
            document=self.document,
            user=self.other_user,
            granted_by=self.owner,
            access_level=DocumentGrant.AccessLevel.READ,
        )
        DocumentGrant.objects.create(
            document=self.document,
            user=self.viewer,
            granted_by=self.owner,
            access_level=DocumentGrant.AccessLevel.EDIT,
        )
        self.client.force_login(self.viewer)

        revoke_url = reverse(
            "revoke_document_access",
            kwargs={
                "document_id": self.document.pk,
                "grant_id": grant.pk,
            },
        )
        response = self.client.post(revoke_url)

        self.assertEqual(response.status_code, 403)
        grant.refresh_from_db()
        self.assertIsNone(grant.revoked_at)

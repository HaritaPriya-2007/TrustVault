
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from .models import AuditEvent
from .services import calculate_event_hash, verify_audit_chain


class AuditHashChainTests(TestCase):
    def create_event(self, action="UPLOAD", details=None):
        return AuditEvent.objects.create(
            action=action,
            success=True,
            details=details or {},
        )

    def test_first_event_has_valid_hash_and_empty_previous_hash(self):
        event = self.create_event()

        self.assertEqual(event.previous_hash, "")
        self.assertEqual(event.event_hash, calculate_event_hash(event))

    def test_second_event_links_to_first_event(self):
        first = self.create_event(action="UPLOAD")
        second = self.create_event(action="DOWNLOAD")

        self.assertEqual(second.previous_hash, first.event_hash)

    def test_valid_chain_passes_verification(self):
        self.create_event(action="UPLOAD")
        self.create_event(action="DOWNLOAD")

        is_valid, errors = verify_audit_chain()

        self.assertTrue(is_valid, errors)
        self.assertEqual(errors, [])

    def test_modified_details_are_detected(self):
        event = self.create_event(details={"filename": "report.pdf"})

        AuditEvent.objects.filter(pk=event.pk).update(
            details={"filename": "changed.pdf"}
        )

        is_valid, errors = verify_audit_chain()

        self.assertFalse(is_valid)
        self.assertTrue(errors)

    def test_broken_previous_hash_is_detected(self):
        self.create_event(action="UPLOAD")
        second = self.create_event(action="DOWNLOAD")

        AuditEvent.objects.filter(pk=second.pk).update(
            previous_hash="broken-hash"
        )

        is_valid, errors = verify_audit_chain()

        self.assertFalse(is_valid)
        self.assertTrue(errors)


class AuditLogAccessTests(TestCase):
    def setUp(self):
        self.audit_url = reverse("audit:audit_log")

        self.admin = User.objects.create_user(
            username="audit_admin",
            password="test-password-admin",
            role=User.Role.ADMIN,
        )
        self.viewer = User.objects.create_user(
            username="audit_viewer",
            password="test-password-viewer",
            role=User.Role.VIEWER,
        )

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(self.audit_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_regular_user_is_forbidden_from_audit_log(self):
        self.client.force_login(self.viewer)

        response = self.client.get(self.audit_url)

        self.assertEqual(response.status_code, 403)

    def test_denied_audit_log_access_is_recorded(self):
        self.client.force_login(self.viewer)

        response = self.client.get(self.audit_url)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            AuditEvent.objects.filter(
                actor=self.viewer,
                action=AuditEvent.Action.ACCESS_DENIED,
                success=False,
                details__operation="audit_log",
            ).exists()
        )

    def test_admin_can_open_audit_log(self):
        self.client.force_login(self.admin)

        response = self.client.get(self.audit_url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_admin"])

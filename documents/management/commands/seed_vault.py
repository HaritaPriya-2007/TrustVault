from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from documents.models import Document, DocumentGrant


DEMO = {
    "admin": {
        "username": "clerk.admin",
        "password": "Seal-Admin-42",
        "role": User.Role.ADMIN,
        "email": "admin@trustvault.local",
    },
    "owner": {
        "username": "owner.mira",
        "password": "Seal-Owner-42",
        "role": User.Role.OWNER,
        "email": "mira@trustvault.local",
    },
    "viewer": {
        "username": "viewer.josef",
        "password": "Seal-Viewer-42",
        "role": User.Role.VIEWER,
        "email": "josef@trustvault.local",
    },
}


class Command(BaseCommand):
    help = "Create demo accounts and a small set of vault documents."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-demo",
            action="store_true",
            help="Delete previously seeded demo documents before creating them again.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        people = {}
        for key, spec in DEMO.items():
            user, created = User.objects.get_or_create(
                username=spec["username"],
                defaults={
                    "email": spec["email"],
                    "role": spec["role"],
                    "is_staff": spec["role"] == User.Role.ADMIN,
                    "is_superuser": spec["role"] == User.Role.ADMIN,
                },
            )
            user.role = spec["role"]
            user.email = spec["email"]
            user.set_password(spec["password"])
            if spec["role"] == User.Role.ADMIN:
                user.is_staff = True
                user.is_superuser = True
            user.save()
            people[key] = user
            self.stdout.write(
                f"{'created' if created else 'updated'} {user.username} ({user.role})"
            )

        owner = people["owner"]
        viewer = people["viewer"]

        if options["reset_demo"]:
            Document.objects.filter(owner=owner, title__startswith="[demo]").delete()

        contract, _ = Document.objects.get_or_create(
            owner=owner,
            title="[demo] Q3 contractor letter",
            defaults={
                "category": "HR",
                "description": "Salary letter used only for the public demo.",
                "original_filename": "q3-contractor-letter.txt",
                "content_type": "text/plain",
                "size_bytes": 0,
            },
        )
        if not contract.file:
            payload = b"Demo salary letter. Not a real employee record.\n"
            contract.size_bytes = len(payload)
            contract.file.save("letter.txt", ContentFile(payload), save=True)

        drawing, _ = Document.objects.get_or_create(
            owner=owner,
            title="[demo] Site plan excerpt",
            defaults={
                "category": "Contracts",
                "description": "A tiny text stand-in for a drawing.",
                "original_filename": "site-plan-excerpt.txt",
                "content_type": "text/plain",
                "size_bytes": 0,
            },
        )
        if not drawing.file:
            payload = b"Demo site plan excerpt. Not a real drawing.\n"
            drawing.size_bytes = len(payload)
            drawing.file.save("plan.txt", ContentFile(payload), save=True)

        DocumentGrant.objects.update_or_create(
            document=contract,
            user=viewer,
            defaults={
                "granted_by": owner,
                "access_level": DocumentGrant.AccessLevel.READ,
                "revoked_at": None,
            },
        )

        self.stdout.write(self.style.SUCCESS("Demo vault is ready."))
        self.stdout.write("Sign in with clerk.admin / owner.mira / viewer.josef")

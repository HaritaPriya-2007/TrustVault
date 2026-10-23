import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class VaultDocumentStorage(FileSystemStorage):
    """
    Keep uploaded files in PRIVATE_DOCUMENT_ROOT, resolved at request time.

    Location is read from settings on every use so tests can isolate storage
    without writing into the developer's real vault directory.
    """

    def __init__(self):
        super().__init__(location=os.path.join(os.getcwd(), "_vault_placeholder"))

    @property
    def base_location(self):
        return str(settings.PRIVATE_DOCUMENT_ROOT)

    @base_location.setter
    def base_location(self, value):
        self._base_location = value

    @property
    def location(self):
        path = os.path.abspath(self.base_location)
        os.makedirs(path, exist_ok=True)
        return path

    @location.setter
    def location(self, value):
        self._location = value


vault_document_storage = VaultDocumentStorage()

"""Filesystem-backed wellness repository implementation."""

from database.interfaces.wellness_repository_interface import WellnessRepository
from database import wellness_repository


class FilesystemWellnessRepository(WellnessRepository):
    """JSON wellness storage layout."""

    def load_wellness(self, account_dir):
        return wellness_repository.load_wellness(account_dir)

    def save_wellness(self, account_dir, wellness):
        return wellness_repository.save_wellness(account_dir, wellness)

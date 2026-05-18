"""Filesystem-backed wellness repository implementation."""

from database.interfaces.wellness_repository_interface import WellnessRepository
from database import wellness_repository as legacy_wellness_repository


class FilesystemWellnessRepository(WellnessRepository):
    """Preserve the current JSON/pickle wellness storage layout."""

    def load_wellness(self, account_dir):
        return legacy_wellness_repository.load_wellness(account_dir)

    def save_wellness(self, account_dir, wellness):
        return legacy_wellness_repository.save_wellness(account_dir, wellness)

"""Filesystem-backed wellness repository implementation."""

from database.interfaces.wellness_repository_interface import WellnessRepository
from database import account_repository, wellness_repository


class FilesystemWellnessRepository(WellnessRepository):
    """JSON wellness storage layout hidden behind logical usernames."""

    def load_wellness(self, username):
        return wellness_repository.load_wellness(account_repository.user_dir(username))

    def save_wellness(self, username, wellness):
        return wellness_repository.save_wellness(account_repository.user_dir(username), wellness)

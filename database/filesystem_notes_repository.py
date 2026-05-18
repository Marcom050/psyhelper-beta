"""Filesystem-backed therapist-notes repository implementation."""

from database.interfaces.notes_repository_interface import NotesRepository
from database import filesystem_account_repository as legacy_account_repository


class FilesystemNotesRepository(NotesRepository):
    """Preserve the current JSON/pickle therapist-notes storage layout."""

    def load_therapist_notes(self, therapist_username):
        return legacy_account_repository.load_therapist_notes(therapist_username)

    def save_therapist_notes(self, therapist_username, notes):
        return legacy_account_repository.save_therapist_notes(therapist_username, notes)

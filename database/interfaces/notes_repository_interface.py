"""Abstract therapist-notes repository contract for PsyHelper services."""

from abc import ABC, abstractmethod


class NotesRepository(ABC):
    """Persistence boundary for therapist notes."""

    @abstractmethod
    def load_therapist_notes(self, therapist_username):
        """Load notes keyed by client username."""

    @abstractmethod
    def save_therapist_notes(self, therapist_username, notes):
        """Persist notes keyed by client username."""

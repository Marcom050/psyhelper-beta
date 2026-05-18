"""Repository factory selecting the active persistence backend."""

from database import config
from database.filesystem_account_repository import FilesystemAccountRepository
from database.filesystem_notes_repository import FilesystemNotesRepository
from database.filesystem_wellness_repository import FilesystemWellnessRepository


def use_postgresql():
    """Return whether PostgreSQL repositories should be used."""
    return bool(config.USE_POSTGRESQL)


def get_account_repository():
    """Return the configured account repository implementation."""
    if use_postgresql():
        from database.postgres.account_repository_pg import PostgresAccountRepository

        return PostgresAccountRepository()
    return FilesystemAccountRepository()


def get_wellness_repository():
    """Return the configured wellness repository implementation."""
    if use_postgresql():
        from database.postgres.wellness_repository_pg import PostgresWellnessRepository

        return PostgresWellnessRepository()
    return FilesystemWellnessRepository()


def get_notes_repository():
    """Return the configured therapist-notes repository implementation."""
    if use_postgresql():
        from database.postgres.notes_repository_pg import PostgresNotesRepository

        return PostgresNotesRepository()
    return FilesystemNotesRepository()

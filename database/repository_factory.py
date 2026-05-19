"""Repository factory selecting the active persistence backend."""
import logging

from database import config
from database.filesystem_account_repository import FilesystemAccountRepository
from database.filesystem_notes_repository import FilesystemNotesRepository
from database.filesystem_wellness_repository import FilesystemWellnessRepository


logger = logging.getLogger(__name__)


def use_postgresql():
    """Return whether PostgreSQL repositories should be used."""
    return bool(config.USE_POSTGRESQL)


def get_account_repository():
    """Return the configured account repository implementation."""
    if use_postgresql():
        from database.postgres.account_repository_pg import PostgresAccountRepository

        return PostgresAccountRepository()
    logger.warning("Using filesystem account repository as source-of-truth (compatibility mode)")
    return FilesystemAccountRepository()


def get_wellness_repository():
    """Return the configured wellness repository implementation."""
    if use_postgresql():
        from database.postgres.wellness_repository_pg import PostgresWellnessRepository

        return PostgresWellnessRepository()
    logger.warning("Using filesystem wellness repository as source-of-truth (compatibility mode)")
    return FilesystemWellnessRepository()


def get_notes_repository():
    """Return the configured therapist-notes repository implementation."""
    if use_postgresql():
        from database.postgres.notes_repository_pg import PostgresNotesRepository

        return PostgresNotesRepository()
    logger.warning("Using filesystem notes repository as source-of-truth (compatibility mode)")
    return FilesystemNotesRepository()


def get_clinical_repository():
    if use_postgresql():
        from database.postgres.clinical_repository_pg import PostgresClinicalRepository
        return PostgresClinicalRepository()
    from database.filesystem_clinical_repository import FilesystemClinicalRepository
    logger.warning("Using filesystem clinical repository as source-of-truth (compatibility mode)")
    return FilesystemClinicalRepository()

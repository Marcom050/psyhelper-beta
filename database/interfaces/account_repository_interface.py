"""Abstract account repository contract for PsyHelper services."""

from abc import ABC, abstractmethod


class AccountRepository(ABC):
    """Persistence boundary for account data used by service-layer code."""

    @abstractmethod
    def load_account_bundle(self, username):
        """Load profile, messages, and wellness data for ``username``."""

    @abstractmethod
    def save_account_bundle(self, username, profile, messages, wellness):
        """Persist profile, messages, and wellness data for ``username``."""

    @abstractmethod
    def load_user_metadata(self, username):
        """Load account metadata for ``username``."""

    @abstractmethod
    def save_user_metadata(self, username, metadata):
        """Persist account metadata for ``username``."""

    @abstractmethod
    def create_user(
        self,
        username,
        password,
        role="client",
        therapist_username=None,
        subscription_status="inactive",
        profile=None,
        email=None,
        beta_disclaimer_accepted_at=None,
    ):
        """Create a user account."""

    @abstractmethod
    def therapist_email_exists(self, email):
        """Return whether a therapist account already uses ``email``."""

    @abstractmethod
    def client_accounts_for(self, therapist_username):
        """Return clients associated with ``therapist_username``."""

    def get_clients_for_tenant(self, tenant_id):
        """Return client accounts owned by ``tenant_id``."""
        return self.client_accounts_for(tenant_id)

    def get_tenant_owner(self, tenant_id):
        """Return tenant owner account details when available."""
        raise NotImplementedError

    def is_same_tenant(self, user_a, user_b):
        """Return whether two usernames resolve to the same tenant."""
        raise NotImplementedError

    def user_exists(self, username):
        """Return whether ``username`` exists in this backend."""
        raise NotImplementedError

    def verify_password(self, username, password):
        """Verify a user password against this backend."""
        raise NotImplementedError

    def delete_user_account(self, username):
        """Permanently delete account profile, metadata, messages, and wellness data."""
        raise NotImplementedError

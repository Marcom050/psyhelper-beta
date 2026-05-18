"""Abstract wellness repository contract for PsyHelper services."""

from abc import ABC, abstractmethod


class WellnessRepository(ABC):
    """Persistence boundary for wellness data."""

    @abstractmethod
    def load_wellness(self, account_dir):
        """Load wellness data from an account directory."""

    @abstractmethod
    def save_wellness(self, account_dir, wellness):
        """Persist wellness data in an account directory."""

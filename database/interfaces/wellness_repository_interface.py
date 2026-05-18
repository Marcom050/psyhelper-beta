"""Abstract wellness repository contract for PsyHelper services."""

from abc import ABC, abstractmethod


class WellnessRepository(ABC):
    """Persistence boundary for wellness data."""

    @abstractmethod
    def load_wellness(self, username):
        """Load wellness data for a logical username."""

    @abstractmethod
    def save_wellness(self, username, wellness):
        """Persist wellness data for a logical username."""

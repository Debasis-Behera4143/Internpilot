"""Base collector definition for opportunity sources."""

from abc import ABC, abstractmethod
from typing import List
from backend.models.opportunity import Opportunity
from backend.utils.logger import get_logger


class BaseCollector(ABC):
    """Abstract base class for all opportunity collectors/scrapers."""

    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger(f"collector_{name}")

    @abstractmethod
    def collect(self) -> List[Opportunity]:
        """Collect opportunities and return a list of Opportunity models."""
        pass

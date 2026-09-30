"""CSV Opportunity Collector Adapter."""

from pathlib import Path
from typing import List, Union
from backend.collectors.import_collector import ImportCollector
from backend.models.opportunity import Opportunity


class CSVCollector(ImportCollector):
    """Adapter specifically for ingesting opportunities from CSV files."""

    def __init__(self, csv_path: Union[str, Path] = None):
        super().__init__()
        self.csv_path = Path(csv_path) if csv_path else None

    def collect(self) -> List[Opportunity]:
        if self.csv_path:
            if not self.csv_path.exists():
                raise FileNotFoundError(f"Configured CSV file does not exist: {self.csv_path}")
            return self.parse_csv(self.csv_path)
        return super().collect()

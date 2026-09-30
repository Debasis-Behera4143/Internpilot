"""JSON Opportunity Collector Adapter."""

from pathlib import Path
from typing import List, Union
from backend.collectors.import_collector import ImportCollector
from backend.models.opportunity import Opportunity


class JSONCollector(ImportCollector):
    """Adapter specifically for ingesting opportunities from JSON files."""

    def __init__(self, json_path: Union[str, Path] = None):
        super().__init__()
        self.json_path = Path(json_path) if json_path else None

    def collect(self) -> List[Opportunity]:
        if self.json_path:
            if not self.json_path.exists():
                raise FileNotFoundError(f"Configured JSON file does not exist: {self.json_path}")
            return self.parse_json(self.json_path)
        return super().collect()

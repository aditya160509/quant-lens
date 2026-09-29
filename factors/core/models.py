from dataclasses import dataclass
from typing import Optional


@dataclass
class FeatureRequest:
    feature_id: str
    as_of: Optional[str] = None

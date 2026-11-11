from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


@dataclass
class WebNode:
    url: str
    node_type: str
    dangerscore: float = 0.0
    metadata: Dict = field(default_factory=dict)


@dataclass
class AttackVector:
    source: str
    target: str
    vectorType: str
    authReq: bool = False
    desc: str = ""

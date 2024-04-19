from termcolor import colored
from dataclasses import dataclass
from enum import IntEnum
from typing import TypeVar, Generic, Tuple, List, Any
from pathlib import Path

# Logging Utilities
# --------------------------------------------------------------------------------

ERROR = colored("[ERROR]", "red")
INFO = colored("[INFO]", "blue")
SUCCESS = colored("[SUCCESS]", "green")
FAIL = colored("[FAIL]", "red")
WARN = colored("[WARN]", "yellow")

class StatusKind(IntEnum):
    SUCCESS = 0
    INFO = 1
    WARN = 2
    FAIL = 3
    ERROR = 4
    PENDING = 5
    CANCEL = 6

@dataclass
class SourceFileInfo:
    path: Path
    line: int
    column: int

@dataclass
class Status:
    status: StatusKind
    message: str = ""

# --------------------------------------------------------------------------------

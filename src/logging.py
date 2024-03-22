from termcolor import colored
from dataclasses import dataclass
from enum import IntEnum
from typing import TypeVar, Generic, Tuple
from pathlib import Path

# Logging Utilities
# --------------------------------------------------------------------------------

ERROR = colored("[ERROR]", "red")
INFO = colored("[INFO]", "blue")
SUCCESS = colored("[SUCCESS]", "green")
FAIL = colored("[FAIL]", "red")
WARN = colored("[WARN]", "yellow")

class Status(IntEnum):
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

T = TypeVar("T", covariant=False)
D = TypeVar("D", covariant=True)
E = TypeVar("E", covariant=False)

@dataclass
class Result(Generic[T, E]):
    value: T | None = None
    error_value: E | None = None

    def unwrap(self) -> T:
        if self.value is not None:
            return self.value
        raise Exception(f"<Result unwrapped an error: {self.error_value}>")

    def unwrap_or(self, default_value: T) -> T:
        if self.value is not None:
            return self.value
        return default_value

    def unwrap_both(self) -> Tuple[T | None, E | None]:
        return self.value, self.error_value

    def unwrap_or_none(self) -> T | None:
        return self.value

    def error(self) -> E | None:
        return self.error_value

@dataclass
class MessageWrapper(Generic[T]):
    status: T
    message: str = ""

StatusResult = MessageWrapper[Status]

# --------------------------------------------------------------------------------

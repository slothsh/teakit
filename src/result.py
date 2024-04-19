from dataclasses import dataclass
from typing import TypeVar, Generic


# Rust-Style Result
# --------------------------------------------------------------------------------

T = TypeVar("T", covariant=False)
D = TypeVar("D", covariant=True)
E = TypeVar("E", covariant=False)

class ResultMethods(Generic[T, E]):
    def unwrap(self) -> T: ...
    def unwrap_error(self) -> E: ...

class UnwrapError(Exception):
    def __init__(self, *args):
        super().__init__(*args)

@dataclass
class Ok(ResultMethods[T, E]):
    value: T
    def unwrap(self) -> T:
        return self.value
    def unwrap_error(self) -> E:
        raise UnwrapError("unwrapped result with no contained error")

@dataclass
class Err(ResultMethods[T, E]):
    error: E
    def unwrap(self) -> T:
        raise UnwrapError("unwrapped result with no contained value")
    def unwrap_error(self) -> E:
        return self.error

Result = Ok[T, E] | Err[T, E]

# --------------------------------------------------------------------------------

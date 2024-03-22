import re
import subprocess
from typing import List, Tuple, Any, Dict
from enum import IntEnum
from .logging import ERROR
from dataclasses import dataclass

# Makefile Utilities
# --------------------------------------------------------------------------------

class MakefileValueType(IntEnum):
    INT = 1
    FLOAT = 2
    STRING = 3
    BOOL = 4


@dataclass
class MakefileKeyValuePair:
    key: str
    value: str
    value_type: MakefileValueType


def get_makefile_value_type(value: str) -> MakefileValueType:
    if re.match("^\\d+\\.\\d+$", value):
        return MakefileValueType.FLOAT
    elif re.match("^\\d+$", value):
        return MakefileValueType.INT
    elif re.match("true|false", value, flags=re.IGNORECASE):
        return MakefileValueType.BOOL

    return MakefileValueType.STRING


def is_makefile_variable_assignment(text: str) -> bool:
    valid_assignment = re.match("^[A-z0-9_\-]+( +)?(:=|=)( +)?([^ ]+|('|\\\").*('|\\\"))$", text)
    if valid_assignment is not None:
        return True
    return False


def parse_makefile_variable_assigment(text: str) -> MakefileKeyValuePair:
    parts = [t.strip() for t in text.split("=", maxsplit=1) if t.strip() != ""]
    value = parts[1]
    value_type = get_makefile_value_type(value)
    return MakefileKeyValuePair(parts[0], value, value_type)


def get_makefile_recipe_result(recipe: str) -> List[str] | None:
    recipe_result = subprocess.run(["make", "-s", recipe], capture_output=True, text=True)

    if recipe_result.returncode == 0:
        return [c.strip() for c in str(recipe_result.stdout).split("\n")]

    return None


def parse_first_makefile_named_identifier(text: str) -> str | None:
    expression_match = re.match("\\$\\(([A-z_]+[0-9A-z_]*)\\)", text)
    if expression_match is not None:
        return expression_match.group(1)
    return None


def parse_all_makefile_named_identifiers(text: str) -> List[Tuple[int, int, str]] | None:
    expression_matches = re.finditer("\\$\\(([A-z_]+[0-9A-z_]*)\\)", text)
    matches: List[Tuple[int, int, str]] = []

    for match in expression_matches:
        matches.append((match.start(), match.end(), match.group(1)))

    if len(matches) == 0:
        return None

    return matches

def evaluate_all_makefile_named_identifiers(text: str, identifiers_config: Dict[str, str]) -> str | None:
    expressions = parse_all_makefile_named_identifiers(text)
    evaluated_line = text
    offset = 0

    if expressions is not None:
        for start, end, variable in expressions:
            evaluated_line = identifiers_config[variable].join([evaluated_line[:start + offset], evaluated_line[end + offset:]])
            offset += len(identifiers_config[variable]) - (end - start)
    else:
        return None

    return evaluated_line


def parse_makefile_config(evaluate_recipe: str) -> List[MakefileKeyValuePair] | None:
    values: List[MakefileKeyValuePair] = []

    try:
        config_data = get_makefile_recipe_result(evaluate_recipe)
        if config_data is not None:
            for cfg in config_data[:-1]:
                values.append(parse_makefile_variable_assigment(cfg))

    except Exception as error:
        print(ERROR, error)
        return None

    return values

# --------------------------------------------------------------------------------


# Makefile Config Decorator
# --------------------------------------------------------------------------------

def makefileconfig(evaluate_config_recipe: str):
    def configure(object: Any):
        config_values = parse_makefile_config(evaluate_config_recipe)

        if config_values is None:
            raise Exception("<makefileconfig failed to parse config>")

        class ProjectConfig(object):
            def __init__(self):
                for config_item in config_values:
                    setattr(self, config_item.key, config_item.value)

            def __getitem__(self, item: str):
                return super().__getattribute__(item)

        return ProjectConfig()

    return configure

# --------------------------------------------------------------------------------

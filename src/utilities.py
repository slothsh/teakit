import dill
from multiprocessing import Process
from dataclasses import dataclass
from typing import List, Any

# General Utilities
# --------------------------------------------------------------------------------

@dataclass
class SliceRange:
    start: int
    end: int


def partition(data: List[Any], max_partitions: int) -> List[List[Any]]:
    if max_partitions < 1:
        raise Exception(f"failed to parition list with partition size of {max_partitions}, partition size must be greater than 0")

    partitions = max_partitions - max(0, max_partitions - len(data))
    partition_data = [[] for _ in range(partitions)]
    for i, v in enumerate(data):
        partition_data[i % partitions].append(v)

    return partition_data

# --------------------------------------------------------------------------------


# Dill Process Utilities
# --------------------------------------------------------------------------------

class DillProcess(Process):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._target = dill.dumps(self._target)

    def run(self):
        if self._target:
            self._target = dill.loads(self._target, ignore=False)

# --------------------------------------------------------------------------------

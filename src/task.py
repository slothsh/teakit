from queue import Empty
from typing import Callable, Iterator, Tuple, Any, List, TypedDict, Self, Set
from dataclasses import dataclass
from enum import Enum
from .logging import Status, StatusKind
from .result import Result, Ok, Err
from .utilities import partition
from multiprocessing import Manager, Process, Queue
from multiprocessing.managers import DictProxy, ListProxy
from hashlib import sha256

# Task Utilities
# --------------------------------------------------------------------------------

class TaskIdentifier(Enum):
    @staticmethod
    def task_hash(identifier: Tuple[int, str]) -> int:
        hasher = sha256()
        hasher.update(identifier[0].to_bytes(identifier[0].bit_length() + 7 // 8, "big"))
        hasher.update(bytes(identifier[1], "utf-8"))
        return int.from_bytes(hasher.digest(), "big")

    @staticmethod
    def task_id(identifier: Tuple[int, str]) -> int:
        return identifier[0]

    @staticmethod
    def task_context(identifier: Tuple[int, str]) -> str:
        return identifier[1]

    @staticmethod
    def get_value(identifier: Any | Tuple[int, str]):
        if isinstance(identifier, tuple):
            return identifier
        return identifier.value

class TaskLog(TypedDict):
    pending: List[TaskIdentifier]
    failed: List[TaskIdentifier]
    completed: List[TaskIdentifier]


@dataclass
class TaskMessenger:
    signature: int
    queue: Queue

    def send_progress(self, progress: float) -> Status:
        self.queue.put((self.signature, progress))
        return Status(StatusKind.SUCCESS, "")

# --------------------------------------------------------------------------------


# Task Object
# --------------------------------------------------------------------------------

@dataclass
class Task:
    action: Callable[..., Tuple[Any, Status]]
    identifier: TaskIdentifier | Tuple[int, str]
    args: Tuple[Any, ...] = ()
    dependencies: Set[TaskIdentifier | Tuple[int, str]] | None = None
    outputs: Any | None = None

    def __post_init__(self):
        self.resolve_dependencies()

    def execute(self, messenger: TaskMessenger, resources: dict[int, Any] = {}) -> Status:
        try:
            resolved_result = self.resolve_arguments(resources)
            match resolved_result:
                case Ok(resolved_arguments):
                    output, result = self.action(messenger, *resolved_arguments)
                    if result.kind == StatusKind.SUCCESS and output is not None:
                        self.outputs = output
                    return result
                case Err(error):
                    return error

        except Exception as error:
            return Status(StatusKind.FAIL, f"failed to execute task \"{self.id_with_context()}\" during task execution with message: {error}")

    def resolve_arguments(self, resources: dict[int, Any]) -> Result[List[Any], Status]:
        all_args = [*self.args]
        resolved: List[Any] = []
        for i, a in enumerate(all_args):
            if isinstance(a, OutputFrom):
                task_value = TaskIdentifier.get_value(a.id)
                task_hash = TaskIdentifier.task_hash(task_value)
                if task_hash not in resources:
                    id = TaskIdentifier.task_id(task_value)
                    context = TaskIdentifier.task_context(task_value)
                    return Err(Status(StatusKind.FAIL, f"cancelled execution of task \"{self.id_with_context()}\" because required inputs were unavailable in resource pool for task \"{id}: {context}\""))
                resolved.append(resources[task_hash])
            else:
                resolved.append(a)

        return Ok(resolved)

    def resolve_dependencies(self) -> Status:
        all_args = [*self.args]
        for i, a in enumerate(all_args):
            if isinstance(a, OutputFrom):
                if self.dependencies is None:
                    self.dependencies = set({})
                self.dependencies.add(a.id)
        return Status(StatusKind.SUCCESS, "")

    def dependencies_satisified(self, completed_dependencies: List[TaskIdentifier]) -> bool:
        if self.dependencies is not None:
            for my_dependency in self.dependencies:
                if my_dependency not in completed_dependencies:
                    return False
        return True

    def id_as_str(self) -> str:
        if isinstance(self.identifier, tuple):
            return f"{TaskIdentifier.task_hash(self.identifier)}"
        return f"{TaskIdentifier.task_hash(self.identifier.value)}"

    def id_as_int(self) -> int:
        if isinstance(self.identifier, tuple):
            return TaskIdentifier.task_hash(self.identifier)
        return TaskIdentifier.task_hash(self.identifier.value)

    def id_with_context(self) -> str:
        if isinstance(self.identifier, tuple):
            return f"{TaskIdentifier.task_id(self.identifier)}{f': {TaskIdentifier.task_context(self.identifier)}' if TaskIdentifier.task_context(self.identifier) != '' else ''}"
        return f"{TaskIdentifier.task_id(self.identifier.value)}{f': {TaskIdentifier.task_context(self.identifier.value)}' if TaskIdentifier.task_context(self.identifier.value) != '' else ''}"


# Task Utilities
# --------------------------------------------------------------------------------

@dataclass
class OutputFrom:
        id: TaskIdentifier | Tuple[int, str]

# --------------------------------------------------------------------------------


# Task Graph Object
# --------------------------------------------------------------------------------

class TaskGraph:
    def __init__(self, tasks: List[Task], depth: int = 0):
        self.tasks: List[Task] = tasks
        self.next: TaskGraph | None = None
        self.depth = depth
        self._iter_depth = 0

    @classmethod
    def from_tasks(cls, tasks: List[Task]) -> Result[Self, Status]:
        root = cls([])

        # Find independent tasks and insert at root
        offset = 0
        length = len(tasks)
        i = 0
        while i - offset < length:
            if tasks[i - offset].dependencies is None:
                task = tasks.pop(i - offset)
                root.tasks.append(task)
                offset += 1
                length -= 1
            i += 1
        if len(root.tasks) == 0:
            return Err(Status(StatusKind.FAIL, "<TaskGraph: no root nodes>"))
        else:
            try:
                passes = 0
                while len(tasks) > 0 and passes < 2:
                    reset = False
                    for i, current_task in enumerate(tasks):
                        if current_task.dependencies is not None:
                            found = 0
                            deepest = 0
                            for current_dependency in current_task.dependencies:
                                depth = 0
                                while depth <= root.total_depth():
                                    for _graph_depth, graph_task in root.tasks_at(depth):
                                        if TaskIdentifier.task_hash(TaskIdentifier.get_value(current_dependency)) == TaskIdentifier.task_hash(TaskIdentifier.get_value(graph_task.identifier)):
                                            found += 1
                                            deepest = depth if deepest < depth else deepest
                                    depth += 1

                            if found == len(current_task.dependencies):
                                root.insert_at(tasks.pop(i), deepest + 1)
                                reset = True
                            elif found > len(current_task.dependencies):
                                return Err(Status(StatusKind.FAIL, "<TaskGraph excess dependencies found>"))

                    passes = passes + 1 if reset is False else 0

                if passes > 1 or len(tasks) > 0:
                    return Err(Status(StatusKind.FAIL, "<TaskGraph circular or missing dependency>"))
            except Exception as error:
                return Err(Status(StatusKind.FAIL, "<TaskGraph internal exception>"))

        return Ok(root)

    def node_at(self, depth: int = 0):
        if self.depth > depth:
            raise Exception("<TaskGraph invalid depth>")
        if self.depth == depth:
            return self
        if self.depth < depth and self.next is not None:
            return self.next.node_at(depth)
        raise Exception("<TaskGraph node>")

    def tasks_at(self, depth: int = 0) -> Iterator[Tuple[int, Task]]:
        if self.depth > depth:
            raise Exception("<TaskGraph invalid depth>")
        if self.depth == depth:
            return iter([(depth, t) for t in self.tasks])
        if self.depth < depth and self.next is not None:
            return self.next.tasks_at(depth)
        return iter([])

    def insert_at(self, value: Task, depth: int = 0):
        if self.depth == depth:
            self.tasks.append(value)
        elif self.depth < depth and self.next is None:
            self.next = TaskGraph([value], depth=self.depth + 1)
        elif self.next is not None:
            self.next.insert_at(value, depth)

    def total_depth(self):
        if self.next is not None:
            return self.next.total_depth()
        return self.depth

    def print(self):
        for task in self.tasks:
            print(" " * (self.depth * 4), self.depth, task)
        if self.next is not None:
            self.next.print()

    def __iter__(self):
        self._iter_depth = 0
        return self

    def __next__(self):
        if self._iter_depth > self.total_depth():
            raise StopIteration

        tmp = self._iter_depth
        self._iter_depth += 1
        return self.node_at(tmp)

# --------------------------------------------------------------------------------


# Task Executor Object
# --------------------------------------------------------------------------------

TaskExecutorResultEntry = Tuple[int, int, Task, Status]
class TaskExecutorResults(TypedDict):
    success: List[TaskExecutorResultEntry]
    failed: List[TaskExecutorResultEntry]


class TaskExecutor:
    def __init__(self, graph: TaskGraph):
        self.manager = Manager()
        self.graph: TaskGraph = graph
        self.outputs: dict[int, Any] = {}
        self.progress: DictProxy = self.manager.dict({})
        self.messages = self.manager.Queue()
        
    @staticmethod
    def task_process(task: Task, partition_i: int, process_i: int, shared_results, resources: dict[int, Any], messages: Queue):
        try:
            messenger = TaskMessenger(TaskIdentifier.task_hash(TaskIdentifier.get_value(task.identifier)), messages)
            result = task.execute(messenger, resources)
            shared_results.append((partition_i, process_i, task, result))
        except Exception as error:
            shared_results.append((partition_i, process_i, task, Status(StatusKind.FAIL, str(error))))

    @classmethod
    def from_tasks(cls, tasks: List[Task]) -> Result[Self, Status]:
        graph_result = TaskGraph.from_tasks(tasks)
        match graph_result:
            case Ok(graph):
                return Ok(cls(graph))
            case Err(error):
                return Err(Status(error.kind, error.message))
        return Err(Status(StatusKind.ERROR, "<TaskExecutor: failed to construct graph with provided tasks>"))

    def execute(self, max_processes: int = 1):
        for depth, node in enumerate(self.graph):
            partitioned_tasks = partition(node.tasks, max_processes)
            processes: List[Process] = []
            shared_results: ListProxy[Tuple[int, int, Task, Status]] = self.manager.list([])

            for partition_i, part in enumerate(partitioned_tasks):
                for process_i, task in enumerate(part):
                    task_process = Process(target=TaskExecutor.task_process, args=(task, partition_i, process_i, shared_results, self.outputs, self.messages))
                    processes.append(task_process)
                    task_process.start()

            while None in [p.exitcode for p in processes]:
                try:
                    message = self.messages.get(timeout=0.1)
                    key = message[0]
                    progress = message[1]
                    self.progress[key] = progress
                except Empty as empty:
                    pass
                else:
                    pass

            for p in processes:
                p.join()

    def tasks_progress(self) -> DictProxy:
        return self.progress

# --------------------------------------------------------------------------------

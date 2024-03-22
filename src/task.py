from typing import Callable, Iterator, Tuple, Any, List, TypedDict, Self
from dataclasses import dataclass
from enum import IntEnum, Enum
from .logging import ERROR, INFO, WARN, SUCCESS, FAIL
from .logging import Result, StatusResult, Status
from .utilities import partition
from multiprocessing import Manager, Process
from multiprocessing.managers import ListProxy

# Development Database Tasks
# --------------------------------------------------------------------------------

class TaskIdentifier(Enum):
    @staticmethod
    def task_hash(identifier: Tuple[int, str]) -> int:
        return hash(str(identifier[0]) + str(identifier[1]))

    @staticmethod
    def task_id(identifier: Tuple[int, str]) -> int:
        return identifier[0]

    @staticmethod
    def task_context(identifier: Tuple[int, str]) -> str:
        return identifier[1]


class TaskLog(TypedDict):
    pending: List[TaskIdentifier]
    failed: List[TaskIdentifier]
    completed: List[TaskIdentifier]

# --------------------------------------------------------------------------------


# Task Object
# --------------------------------------------------------------------------------

@dataclass
class Task:
    action: Callable[..., StatusResult]
    identifier: TaskIdentifier
    args: Tuple[Any, ...] = ()
    dependencies: List[TaskIdentifier] | None = None

    def execute(self) -> StatusResult:
        try:
            result = self.action(*self.args)
            return result
        except Exception as error:
            return StatusResult(Status.FAIL, f"failed to execute task \"{self.id_with_context()}\" during task execution with message: {error}")

    def dependencies_satisified(self, completed_dependencies: List[TaskIdentifier]) -> bool:
        if self.dependencies is not None:
            for my_dependency in self.dependencies:
                if my_dependency not in completed_dependencies:
                    return False
        return True

    def id(self):
        return f"{TaskIdentifier.task_hash(self.identifier.value)}"

    def id_with_context(self):
        return f"{TaskIdentifier.task_id(self.identifier.value)}{f': {TaskIdentifier.task_context(self.identifier.value)}' if TaskIdentifier.task_context(self.identifier.value) != '' else ''}"


# Task Utilities
# --------------------------------------------------------------------------------

def TaskExecutionWrapper(task: Task, after: Callable[..., None]):
    def execute() -> StatusResult:
        try:
            result = task.execute()
            after(result)
            return result
        except Exception as error:
            result = StatusResult(Status.FAIL, f"failed to execute step during {TaskGroup.__name__} execution with error: {error}")
            after(result)
            return result

    return execute

# --------------------------------------------------------------------------------


# Task Group Object
# --------------------------------------------------------------------------------

class TaskGroup:
    def __init__(self, tasks: List[Task]):
        self.name: str
        self.tasks: List[Task] = tasks

    def __iter__(self):
        return iter(self.tasks)

    def group_name(self) -> str:
        return self.name

    def add_task(self, task: Task):
        if isinstance(task, Task) is False:
            raise Exception(f"could not add task to {TaskGroup.__name__} because {task.__qualname__} was not a valid {Task.__name__}")
        self.tasks.append(task)

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
    def from_tasks(cls, tasks: List[Task]) -> Result[Self, StatusResult]:
        root = TaskGraph([])

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
            return Result(None, StatusResult(Status.FAIL, "<TaskGraph: no root nodes>"))
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
                                        if TaskIdentifier.task_hash(current_dependency.value) == TaskIdentifier.task_hash(graph_task.identifier.value):
                                            found += 1
                                            deepest = depth if deepest < depth else deepest
                                    depth += 1

                            if found == len(current_task.dependencies):
                                root.insert_at(tasks.pop(i), deepest + 1)
                                reset = True
                            elif found > len(current_task.dependencies):
                                return Result(None, StatusResult(Status.FAIL, "<TaskGraph excess dependencies found>"))

                    passes = passes + 1 if reset is False else 0

                if passes > 1 or len(tasks) > 0:
                    return Result(None, StatusResult(Status.FAIL, "<TaskGraph circular or missing dependency>"))
            except Exception as error:
                return Result(None, StatusResult(Status.FAIL, "<TaskGraph internal exception>"))

        return Result(root, None)

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
        else:
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

    def _check_missing_dependencies(self, tasks: List[Task]) -> StatusResult:
        return StatusResult(Status.FAIL, "not implemented")

# --------------------------------------------------------------------------------


# Task Executor Object
# --------------------------------------------------------------------------------

TaskExecutorResultEntry = Tuple[int, int, Task, StatusResult]
class TaskExecutorResults(TypedDict):
    success: List[TaskExecutorResultEntry]
    failed: List[TaskExecutorResultEntry]


class TaskExecutor:
    def __init__(self, graph: TaskGraph):
        self.graph: TaskGraph = graph
        self.results: TaskExecutorResults = {
            "success": [],
            "failed": []
        }
        
    @staticmethod
    def task_process(task: Task, partition_i: int, process_i: int, shared_results):
        try:
            result = task.execute()
            shared_results.append((partition_i, process_i, task, result))
        except Exception as error:
            shared_results.append((partition_i, process_i, task, StatusResult(Status.FAIL, str(error))))

    def execute(self, max_processes: int = 1):
        with Manager() as manager:

            for depth, node in enumerate(self.graph):
                partitioned_tasks = partition(node.tasks, max_processes)
                processes: List[Process] = []
                shared_results: ListProxy[Tuple[int, int, Task, StatusResult]] = manager.list([])

                for partition_i, part in enumerate(partitioned_tasks):
                    for process_i, task in enumerate(part):
                        task_process = Process(target=TaskExecutor.task_process, args=(task, partition_i, process_i, shared_results))
                        processes.append(task_process)
                        task_process.start()
                        task_process.join()

                print(INFO, f"executing {len(processes)} task{'' if len(processes) == 1 else 's'} in layer {depth} of task graph")

                while None in [p.exitcode for i, p in enumerate(processes)]:
                    # TODO: Report Progress
                    pass
                else:
                    for partition_i, process_i, task, result in shared_results:
                        if result.status == Status.SUCCESS:
                            print(SUCCESS, f"task \"{task.id_with_context()}\" completed {' with message: ' + result.message if len(result.message) > 0 else ''}")
                        elif result.status == Status.FAIL:
                            print(FAIL, result.message)

    def insert_result(self, result: TaskExecutorResultEntry):
        if result[3].status == Status.SUCCESS:
            self.results["success"].append(result)
        elif result[3].status == Status.FAIL:
            self.results["success"].append(result)

    def print_result(self, depth: int, id: int, task: Task, result: StatusResult):
        if result.status == Status.SUCCESS:
            print(SUCCESS, f"task {task.id_with_context()} completed successfully")
        elif result.status == Status.FAIL:
            print(FAIL, f"task {task.id_with_context()} has failed")

# --------------------------------------------------------------------------------

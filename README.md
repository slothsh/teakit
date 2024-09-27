# Teakit

A simple task executor library that can be used to procedurally build up a
dependency tree of tasks which can be executed in parallel.

## Usage

### Declare Tasks

Tasks are built-up procedurally, but can also be created programatically.

```python
# Function signatures for `Task` functions
def unevolved(messenger: TaskMessenger, *args): ...

# Declare a task
unevolved_task = Task(
    identifier=(0, "Unevolved Task"), # Tuple elements can be any value, but first element MUST be unique 
    action=unevolved,
    args=("pichu"), # Task messenger is provided internally
    dependencies=None # Don't need to specify explicitally
)
```

Specifying dependencies is done up-front, before execution.

Multiple dependencies can be specified.

```python
def evolution_one(messenger: TaskMessenger, *args): ...

evolution_one_task = Task(
    identifier=(1, "Pika, pika!"),
    action=evolution_one,
    args=("pikachu"),
    dependencies=[unevolved_task] # We specify the `Task` as the dependency, NOT the function the `Task` will execute.
)

def evolution_two(messenger: TaskMessenger, *args): ...

evolution_two_normal_task = Task(
    identifier=(2, "I choose you!"),
    action=evolution_two,
    args=("raichu"),

    dependencies=[evolution_one_task] # Depends on `evolution_one_task` directly, but also
                                      # transiently to `unevolved_task`. You can specify both, regardless.
)

evolution_two_alolan_task = Task(
    identifier=(3, "I choose you!"),
    action=evolution_two, # Functions can be used more than one task
    args=("raichu alolan"),
    dependencies=[evolution_one_task]
)
```

If input of a `Task` depends on the results of prior tasks, then output can be captured
with the `OutputFrom` adapter. Internally, `TaskExecutor` will forward the results of
the specified task:

```python
def evolution_two(messenger: TaskMessenger, *args): ...

evolution_two_task = Task(
    identifier=(4, "I choose you... again!"),
    action=evolution_two,
    args=(OutputFrom(evolution_one_task)),

    dependencies=None # We need not specify dependency on evolution_one_task,
                      # since OutputFrom(evolution_one_task) implicitly means the same thing.
)
```

### Execute Tasks

The above tasks, once the task graph is constructed, will have the following topology:

```python
# Root:                  (unevolved)
#                             |
#                             v
# Layer 1:              (evolution_one)
#                       /             \
#                      v               v
# Layer 2: (evolution_two_normal) (evolution_two_alolan)
```

When a max process count of `2` is specified (2 sub-processes will be spawned per layer),
then the above graph will be executed in the following order:

```python
# Order:            1               2                                   3
# Sub-Process:      1               1                       1                        2
# Task:        `unevolved` -> `evolution_one` -> `evolution_two_normal` + `evolution_two_alolan`
```

We build `TaskGraph` by constructing `TaskExecutor`.

Executing `TaskExecutor` will block the current thread, but you can offload
execution to a separate thread in your application code.

```python
    pikachu_evolution = TaskExecutor.from_tasks([evolution_two_task, evolution_three_task, evolution_one_task]) # Order doesn't matter

    match pikachu_evolution:
        case Ok(executor):
            executor.execute(max_processes=4) # Blocks current thread until all `Tasks` complete.
        case Err(error):
            print(error.message)
```

### Task Functions

`Task` functions must be defined with the interface `my_task_function(messenger: TaskMessenger, *args)`,
and then `*args` can be dynamically unpacked in the body of `my_task_function`:

**NOTE: Take care to handle errors being raised when unpacking a non-existent value in `*args`.**
**      The order of arguments in `*args` is forwarded in the same order as specified when the `Task`**
**      was constructed.**

```python
def my_task_function(messenger: TaskMessenger, *args):
    if len(args) != 1:
        return

    pokemon: str = args[0]
    # ...
```

A channel for inter-process communication is provided as the first argument to each `Task`,
which can optionally be used to report progress of execution to the `TaskExecutor`.
The first argument is a normalized floating-point number representing the progress,
and the second argument is a string used as context.

If a task terminates successfully, i.e. without raising an exception, and the progress
has not been set to 1.0 during the course of the function body, then the `TaskExecutor`
will default to 1.0 on success.

Abnormal termination of a `Task` will maintain the last reported progress and a failed
flag will be set for the `Task` by the `TaskExecutor`.

```python
def my_task_function(messenger: TaskMessenger, *args):
    pokemon: str = args[0]

    # Some work ...

    messenger.send_progress(0.5, "Processing pokemon evolution")

    # More work...

    messenger.send_progress(1.0, "Pokemon evolution complete")
```

___

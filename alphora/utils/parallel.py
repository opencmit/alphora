import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List, Optional, Tuple, Dict, Union


def parallel_run(
        calls: List[Union[
            Any,
            Tuple[Any, Tuple],
            Tuple[Any, Tuple, Dict[str, Any]],
        ]],
        method_name: str,
        timeout: Optional[float] = None,
) -> List[Any]:
    if not calls:
        return []

    normalized_calls: List[Tuple[Any, Tuple, Dict[str, Any]]] = []
    for item in calls:
        if isinstance(item, tuple):
            if len(item) == 1:
                normalized_calls.append((item[0], (), {}))
            elif len(item) == 2:
                normalized_calls.append((item[0], item[1], {}))
            elif len(item) == 3:
                normalized_calls.append((item[0], item[1], item[2]))
            else:
                raise ValueError(f"Invalid call spec: {item}")
        else:
            normalized_calls.append((item, (), {}))

    objects = [obj for obj, _, _ in normalized_calls]
    first_method = getattr(objects[0], method_name, None)
    if first_method is None:
        raise AttributeError(f"Object {objects[0]} has no method '{method_name}'")

    if asyncio.iscoroutinefunction(first_method):
        return _run_async_methods(normalized_calls, method_name, timeout)
    else:
        return _run_sync_methods(normalized_calls, method_name, timeout)


def _run_async_methods(calls: List[Tuple[Any, Tuple, Dict[str, Any]]], method_name: str, timeout: Optional[float]):
    async def _call(obj, args, kwargs):
        method = getattr(obj, method_name)
        coro = method(*args, **kwargs)
        if timeout is not None:
            return await asyncio.wait_for(coro, timeout=timeout)
        return await coro

    async def _gather():
        return await asyncio.gather(*[_call(obj, args, kwargs) for obj, args, kwargs in calls])

    try:
        return asyncio.run(_gather())
    except RuntimeError as e:
        if "event loop is running" in str(e):
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(_gather())
        raise


def _run_sync_methods(calls: List[Tuple[Any, Tuple, Dict[str, Any]]], method_name: str, timeout: Optional[float]):
    def _call(obj, args, kwargs):
        method = getattr(obj, method_name)
        return method(*args, **kwargs)

    with ThreadPoolExecutor(max_workers=len(calls)) as executor:
        futures = [executor.submit(_call, obj, args, kwargs) for obj, args, kwargs in calls]
        return [f.result(timeout=timeout) for f in futures]


def parallel_run_heterogeneous(
        calls: List[Union[
            Tuple[Any, str],
            Tuple[Any, str, Tuple],
            Tuple[Any, str, Tuple, Dict[str, Any]],
        ]],
        timeout: Optional[float] = None,
) -> List[Any]:
    if not calls:
        return []

    normalized_calls: List[Tuple[Any, str, Tuple, Dict[str, Any]]] = []
    for item in calls:
        if not isinstance(item, tuple):
            raise ValueError("Each call must be a tuple")
        n = len(item)
        if n == 2:
            normalized_calls.append((item[0], item[1], (), {}))
        elif n == 3:
            normalized_calls.append((item[0], item[1], item[2], {}))
        elif n == 4:
            normalized_calls.append((item[0], item[1], item[2], item[3]))
        else:
            raise ValueError(f"Invalid heterogeneous call spec with {n} elements: {item}")

    sync_tasks: List[Tuple[int, Any, str, Tuple, Dict[str, Any]]] = []
    async_tasks: List[Tuple[int, Any, str, Tuple, Dict[str, Any]]] = []

    for idx, (obj, method_name, args, kwargs) in enumerate(normalized_calls):
        method = getattr(obj, method_name, None)
        if method is None:
            raise AttributeError(f"Object {obj} has no method '{method_name}'")
        if asyncio.iscoroutinefunction(method):
            async_tasks.append((idx, obj, method_name, args, kwargs))
        else:
            sync_tasks.append((idx, obj, method_name, args, kwargs))

    results = [None] * len(normalized_calls)

    if async_tasks:
        async_results = _run_async_heterogeneous(async_tasks, timeout)
        for task, res in zip(async_tasks, async_results):
            results[task[0]] = res

    if sync_tasks:
        sync_results = _run_sync_heterogeneous(sync_tasks, timeout)
        for task, res in zip(sync_tasks, sync_results):
            results[task[0]] = res

    return results


async def _execute_async_call(obj, method_name, args, kwargs, timeout):
    method = getattr(obj, method_name)
    coro = method(*args, **kwargs)
    if timeout is not None:
        return await asyncio.wait_for(coro, timeout=timeout)
    return await coro


async def _gather_async_heterogeneous(tasks, timeout):
    coros = [
        _execute_async_call(obj, method, args, kwargs, timeout)
        for (_, obj, method, args, kwargs) in tasks
    ]
    return await asyncio.gather(*coros, return_exceptions=False)


def _run_async_heterogeneous(tasks, timeout):
    try:
        return asyncio.run(_gather_async_heterogeneous(tasks, timeout))
    except RuntimeError as e:
        if "event loop is running" in str(e):
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(_gather_async_heterogeneous(tasks, timeout))
        raise


def _execute_sync_call(obj, method_name, args, kwargs):
    method = getattr(obj, method_name)
    return method(*args, **kwargs)


def _run_sync_heterogeneous(tasks, timeout):
    def worker(task):
        _, obj, method, args, kwargs = task  # 5 elements: (idx, obj, method, args, kwargs)
        return _execute_sync_call(obj, method, args, kwargs)

    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = [executor.submit(worker, task) for task in tasks]
        return [f.result(timeout=timeout) for f in futures]


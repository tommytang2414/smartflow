"""Process-isolated execution for collectors with enforceable wall-clock timeouts."""

import importlib
import multiprocessing
import traceback
from queue import Empty
from typing import Any


class ProcessTimeoutError(TimeoutError):
    pass


class RemoteProcessError(RuntimeError):
    pass


def _resolve_callable(callable_path: str):
    module_name, separator, attribute_name = callable_path.partition(":")
    if not separator or not module_name or not attribute_name:
        raise ValueError("callable_path must use 'module:function' format")
    module = importlib.import_module(module_name)
    return getattr(module, attribute_name)


def _process_entry(callable_path: str, args: tuple, kwargs: dict, result_queue) -> None:
    try:
        result = _resolve_callable(callable_path)(*args, **kwargs)
        result_queue.put(("ok", result))
    except BaseException as error:
        result_queue.put(
            (
                "error",
                type(error).__name__,
                str(error),
                traceback.format_exc(),
            )
        )


def run_in_process(
    callable_path: str,
    *,
    args: tuple = (),
    kwargs: dict | None = None,
    timeout_seconds: float,
) -> Any:
    """Run an importable callable in a child process and terminate it on timeout."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue(maxsize=1)
    process = context.Process(
        target=_process_entry,
        args=(callable_path, args, kwargs or {}, result_queue),
        name=f"smartflow-{callable_path.replace(':', '-')}",
        daemon=False,
    )
    process.start()

    try:
        process.join(timeout_seconds)
        if process.is_alive():
            process.terminate()
            process.join(5)
            if process.is_alive():
                process.kill()
                process.join(5)
            raise ProcessTimeoutError(
                f"{callable_path} exceeded {timeout_seconds:g}s and was terminated"
            )

        try:
            outcome = result_queue.get(timeout=1)
        except Empty as error:
            raise RemoteProcessError(
                f"{callable_path} exited with code {process.exitcode} without a result"
            ) from error

        if outcome[0] == "ok":
            return outcome[1]

        _, error_type, message, remote_traceback = outcome
        raise RemoteProcessError(
            f"{callable_path} failed with {error_type}: {message}\n{remote_traceback}"
        )
    finally:
        if process.is_alive():
            process.kill()
            process.join(5)
        process.close()
        result_queue.close()
        result_queue.join_thread()

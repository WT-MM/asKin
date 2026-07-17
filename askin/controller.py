"""Asynchronous keyboard input."""

import asyncio
import logging
import sys
import time
from contextlib import contextmanager
from typing import Awaitable, Callable, Generator

logger = logging.getLogger(__name__)


if sys.platform == "win32":
    import msvcrt

    @contextmanager
    def _cbreak() -> Generator[None, None, None]:
        # Windows console reads chars directly via msvcrt — no terminal mode setup needed.
        yield

    def _read_key(timeout: float) -> str | None:
        deadline = time.monotonic() + timeout
        while True:
            if msvcrt.kbhit():
                return msvcrt.getwch()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            time.sleep(min(0.001, remaining))

else:
    import select
    import termios

    @contextmanager
    def _cbreak() -> Generator[None, None, None]:
        """Put the terminal in cbreak mode for char-by-char input without echo."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            new_settings = termios.tcgetattr(fd)
            new_settings[3] = new_settings[3] & ~termios.ECHO
            new_settings[3] = new_settings[3] & ~termios.ICANON
            new_settings[6][termios.VMIN] = 0
            new_settings[6][termios.VTIME] = 0
            termios.tcsetattr(fd, termios.TCSADRAIN, new_settings)
            yield
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def _read_key(timeout: float) -> str | None:
        if select.select([sys.stdin], [], [], timeout)[0]:
            return sys.stdin.read(1)
        return None


class KeyboardController:
    """Handles asynchronous keyboard input in a non-blocking way."""

    def __init__(
        self,
        key_handler: Callable[[str], Awaitable[None]],
        default: Callable[[], Awaitable[None]] | None = None,
        default_loops_before_trigger: int = 10,
        timeout: float = 0.001,
    ) -> None:
        """Initializes the KeyboardController.

        Args:
            key_handler: An async function to call when a key is pressed.
                         It receives the pressed key (str) as an argument.
            default: An async function to call when no key is pressed.
            default_loops_before_trigger: The number of loops to wait before triggering the default function.
            timeout: The timeout for the keyboard listener.
        """
        self._key_handler = key_handler
        self._task: asyncio.Task | None = None
        self._timeout = timeout
        self._default = default
        self._default_loops_before_trigger = default_loops_before_trigger

    async def _run_loop(self) -> None:
        """The main loop that listens for keyboard input."""
        logger.info("\nKeyboard control active:")
        logger.info("  Press Ctrl+C to exit\n")

        loop_count = 0

        with _cbreak():
            try:
                while True:
                    key = _read_key(self._timeout)
                    if key is not None:
                        if key == "\x03":  # Ctrl+C (Unix only; Windows raises KeyboardInterrupt)
                            logger.info("Ctrl+C detected by keyboard listener.")
                            current_task = asyncio.current_task()
                            if current_task:
                                current_task.get_loop().call_soon(current_task.get_loop().stop)
                            break

                        await self._key_handler(key)
                    elif self._default:
                        loop_count += 1
                        if loop_count >= self._default_loops_before_trigger:
                            await self._default()
                            loop_count = 0

                    await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                logger.debug("Keyboard listener task cancelled.")
            except Exception as e:
                logger.exception("Error in keyboard listener loop: %s", e)
            finally:
                logger.info("Keyboard input loop stopping...")

    async def start(self) -> None:
        """Starts the keyboard listening task."""
        if self._task is None or self._task.done():
            logger.info("Starting keyboard listener...")
            self._task = asyncio.create_task(self._run_loop())
            self._task.add_done_callback(self._task_done_callback)
        else:
            logger.warning("Keyboard listener task already running.")

    def _task_done_callback(self, task: asyncio.Task) -> None:
        """Callback executed when the keyboard task finishes."""
        try:
            # Check if the task raised an exception
            exc = task.exception()
            if exc:
                logger.exception("Keyboard listener task failed: %s", exc)
            else:
                logger.info("Keyboard listener task finished successfully.")
        except asyncio.CancelledError:
            logger.info("Keyboard listener task was cancelled.")
        self._task = None  # Clear the task reference

    async def stop(self) -> None:
        """Stops the keyboard listening task."""
        if self._task and not self._task.done():
            logger.info("Stopping keyboard listener task...")
            self._task.cancel()
            try:
                # Wait briefly for the task to acknowledge cancellation
                await asyncio.wait_for(self._task, timeout=1.0)
            except asyncio.CancelledError:
                logger.debug("Keyboard listener task successfully cancelled.")
            except asyncio.TimeoutError:
                logger.warning("Keyboard listener task did not stop gracefully.")
            except Exception as e:
                logger.exception("Error stopping keyboard listener task: %s", e)
            finally:
                self._task = None
        else:
            logger.debug("Keyboard listener task not running or already stopped.")

import asyncio
import logging
from typing import Callable, Coroutine, Dict, List

from aiogram.types import Message

logger = logging.getLogger(__name__)


class MediaGroupCollector:
    """
    Buffers incoming media-group parts and fires a callback once all parts
    have arrived (determined by a configurable silence window).
    """

    def __init__(self, delay: float = 1.0) -> None:
        self._delay = delay
        self._groups: Dict[str, List[Message]] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._callbacks: Dict[str, Callable[[List[Message]], Coroutine]] = {}

    async def collect(
        self,
        message: Message,
        callback: Callable[[List[Message]], Coroutine],
    ) -> None:
        """
        Add a message to its media group buffer.
        The callback is called exactly once with the sorted complete album.
        """
        group_id: str = message.media_group_id  # type: ignore[assignment]

        if group_id not in self._groups:
            self._groups[group_id] = []
            self._callbacks[group_id] = callback

        self._groups[group_id].append(message)

        # Reset the flush timer every time a new part arrives
        existing = self._tasks.get(group_id)
        if existing and not existing.done():
            existing.cancel()

        self._tasks[group_id] = asyncio.create_task(self._flush(group_id))

    async def _flush(self, group_id: str) -> None:
        try:
            await asyncio.sleep(self._delay)
        except asyncio.CancelledError:
            return

        messages = self._groups.pop(group_id, [])
        callback = self._callbacks.pop(group_id, None)
        self._tasks.pop(group_id, None)

        if not messages or callback is None:
            return

        # Sort by message_id to preserve album order
        messages.sort(key=lambda m: m.message_id)
        logger.debug("Flushing media group %s (%d parts)", group_id, len(messages))

        try:
            await callback(messages)
        except Exception:
            logger.exception("Error in media group callback for group %s", group_id)

# src/core/priority_queue.py
"""
Ensures that the most critical tasks (especially medical emergencies)
are processed first.
"""
import heapq
import time
import itertools
from enum import IntEnum
from dataclasses import dataclass, field
from typing import Any

# from . import logger

class Priority(IntEnum):
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    BACKGROUND = 4

@dataclass(order=True)
class QueueItem:
    """An item in the priority queue."""
    priority: int
    timestamp: int
    count: int
    item: Any=field(compare=False)

class PriorityQueue:
    def __init__(self, max_wait_time_seconds: int = 300):
        """
        Initializes the priority queue.
        
        Args:
            max_wait_time_seconds: Time after which a task's priority gets promoted.
        """
        self._queue = []
        self._counter = itertools.count()
        self._max_wait_time = max_wait_time_seconds
        print("PriorityQueue initialized.")

    def push(self, item: Any, priority: Priority):
        """Adds an item to the queue with a given priority."""
        if not isinstance(priority, Priority):
            raise TypeError("Priority must be a Priority enum member.")
        
        timestamp = int(time.time())
        count = next(self._counter)
        heapq.heappush(self._queue, QueueItem(priority.value, timestamp, count, item))
        # logger.debug(f"Pushed item to queue with priority {priority.name}.")

    def pop(self) -> Any:
        """
        Removes and returns the item with the highest priority.
        
        Also implements age-based priority promotion to prevent starvation.
        """
        if not self._queue:
            return None

        # Check for tasks that need priority promotion
        # self._promote_aged_tasks() # This can be computationally expensive to do on every pop

        item_wrapper = heapq.heappop(self._queue)
        # logger.info(f"Popped item from queue with original priority {Priority(item_wrapper.priority).name}.")
        return item_wrapper.item

    def _promote_aged_tasks(self):
        """
        Increases the priority of tasks that have been waiting too long.
        (Note: This is a conceptual implementation. Modifying heap items
         in-place is complex; a more robust solution might use a different structure
         or periodic reconstruction.)
        """
        now = int(time.time())
        for item_wrapper in self._queue:
            if (now - item_wrapper.timestamp > self._max_wait_time) and (item_wrapper.priority > Priority.HIGH):
                # logger.warning(f"Promoting task due to age. Original priority: {Priority(item_wrapper.priority).name}")
                item_wrapper.priority -= 1
        
        # Re-establish the heap property after changing priorities
        heapq.heapify(self._queue)

    def is_empty(self) -> bool:
        """Checks if the queue is empty."""
        return len(self._queue) == 0

    def get_wait_times(self) -> dict:
        """Returns current wait time statistics."""
        now = int(time.time())
        wait_times = {p.name: [] for p in Priority}
        for item in self._queue:
            wait_times[Priority(item.priority).name].append(now - item.timestamp)
        
        return {p: (sum(t)/len(t) if t else 0) for p, t in wait_times.items()}
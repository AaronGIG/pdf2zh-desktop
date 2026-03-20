# thanks to:
# https://github.com/oleglpts/PriorityThreadPoolExecutor/blob/master/PriorityThreadPoolExecutor/__init__.py
# https://github.com/oleglpts/PriorityThreadPoolExecutor/issues/4

import atexit
import itertools
import logging
import queue
import random
import sys
import threading
import weakref
from concurrent.futures import _base
from concurrent.futures.thread import BrokenThreadPool
from concurrent.futures.thread import ThreadPoolExecutor
from concurrent.futures.thread import _python_exit
from concurrent.futures.thread import _threads_queues
from concurrent.futures.thread import _WorkItem
from heapq import heappop
from heapq import heappush

logger = logging.getLogger(__name__)

########################################################################################################################
#                                                Global variables                                                      #
########################################################################################################################

NULL_ENTRY = (sys.maxsize, _WorkItem(None, None, (), {}))
_shutdown = False

########################################################################################################################
#                                           Before system exit procedure                                               #
########################################################################################################################


def python_exit():
    """

    Cleanup before system exit

    """
    global _shutdown
    _shutdown = True
    items = list(_threads_queues.items())
    for _t, q in items:
        q.put(NULL_ENTRY)
    for t, _q in items:
        t.join()


# change default cleanup


atexit.unregister(_python_exit)
atexit.register(python_exit)


class PriorityQueue(queue.Queue):
    """Variant of Queue that retrieves open entries in priority order (lowest first).

    Entries are typically tuples of the form:  (priority number, data).
    """

    REMOVED = "<removed-task>"
    DEFAULT_PRIORITY = 100

    def _init(self, maxsize):
        self.queue = []
        self.entry_finder = {}
        self.counter = itertools.count()

    def _qsize(self):
        return len(self.queue)

    def _put(self, item):
        # heappush(self.queue, item)
        try:
            if item[1] in self.entry_finder:
                self.remove(item[1])
            count = next(self.counter)
            entry = [item[0], count, item[1]]
            self.entry_finder[item[1]] = entry
            heappush(self.queue, entry)
        except TypeError:  # handle item==None
            self._put((self.DEFAULT_PRIORITY, None))

    def remove(self, task):
        """
        This simply replaces the data with the REMOVED value,
        which will get cleared out once _get reaches it.
        """
        entry = self.entry_finder.pop(task)
        entry[-1] = self.REMOVED

    def _get(self):
        while self.queue:
            entry = heappop(self.queue)
            if entry[2] is not self.REMOVED:
                del self.entry_finder[entry[2]]
                return entry
        return None


def _worker(executor_reference, work_queue, initializer, initargs):
    if initializer is not None:
        try:
            initializer(*initargs)
        except BaseException:
            _base.LOGGER.critical("Exception in initializer:", exc_info=True)
            executor = executor_reference()
            if executor is not None:
                executor._initializer_failed()
            return
    try:
        while True:
            work_item = work_queue.get(block=True)
            try:
                if work_item[2] is not None:
                    work_item[2].run()
                    # Delete references to object. See issue16284
                    del work_item

                    # attempt to increment idle count
                    executor = executor_reference()
                    if executor is not None:
                        executor._idle_semaphore.release()
                    del executor
                    continue

                executor = executor_reference()
                # Exit if:
                #   - The interpreter is shutting down OR
                #   - The executor that owns the worker has been collected OR
                #   - The executor that owns the worker has been shutdown.
                if _shutdown or executor is None or executor._shutdown:
                    # Flag the executor as shutting down as early as possible if it
                    # is not gc-ed yet.
                    if executor is not None:
                        executor._shutdown = True
                    # Notice other workers
                    work_queue.put(None)
                    return
                del executor
            finally:
                work_queue.task_done()
    except BaseException:
        _base.LOGGER.critical("Exception in worker", exc_info=True)


class PriorityThreadPoolExecutor(ThreadPoolExecutor):
    """
    Thread pool executor with priority queue (priorities must be different, lowest first)
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # change work queue type to queue.PriorityQueue
        self._work_queue: PriorityQueue = PriorityQueue()

    def submit(self, fn, *args, **kwargs):
        """

        Sending the function to the execution queue

        :param fn: function being executed
        :type fn: callable
        :param args: function's positional arguments
        :param kwargs: function's keywords arguments
        :return: future instance
        :rtype: _base.Future

        Added keyword:

        - priority (integer later sys.maxsize)

        """
        with self._shutdown_lock:
            if self._broken:
                raise BrokenThreadPool(self._broken)

            if self._shutdown:
                raise RuntimeError("cannot schedule new futures after shutdown")
            if _shutdown:
                raise RuntimeError(
                    "cannot schedule new futures after interpreter shutdown"
                )

            priority = kwargs.get("priority", random.randint(0, sys.maxsize - 1))  # noqa: S311
            if "priority" in kwargs:
                del kwargs["priority"]

            f = _base.Future()
            w = _WorkItem(f, fn, args, kwargs)

            self._work_queue.put((priority, w))
            self._adjust_thread_count()
            return f

    def _adjust_thread_count(self):
        # if idle threads are available, don't spin new threads
        if self._idle_semaphore.acquire(timeout=0):
            return

        # When the executor gets lost, the weakref callback will wake up
        # the worker threads.
        def weakref_cb(_, q=self._work_queue):
            q.put(None)

        num_threads = len(self._threads)
        if num_threads < self._max_workers:
            thread_name = f"{self._thread_name_prefix or self}_{num_threads:d}"
            t = threading.Thread(
                name=thread_name,
                target=_worker,
                args=(
                    weakref.ref(self, weakref_cb),
                    self._work_queue,
                    self._initializer,
                    self._initargs,
                ),
            )
            t.start()
            self._threads.add(t)
            _threads_queues[t] = self._work_queue

    def shutdown(self, wait=True, *, cancel_futures=False):
        logger.debug("Shutting down executor %s", self._thread_name_prefix or self)
        if wait:
            logger.debug(
                "Waiting for all tasks done %s", self._thread_name_prefix or self
            )
            self._work_queue.join()
            logger.debug("All tasks done %s", self._thread_name_prefix or self)

        with self._shutdown_lock:
            self._shutdown = True
            if cancel_futures:
                # Drain all work items from the queue, and then cancel their
                # associated futures.
                while True:
                    try:
                        work_item = self._work_queue.get_nowait()
                    except queue.Empty:
                        break
                    if work_item is not None:
                        work_item.future.cancel()

            # Send a wake-up to prevent threads calling
            # _work_queue.get(block=True) from permanently blocking.
            self._work_queue.put(None)
        if wait:
            logger.debug(
                "Waiting for all thread done %s", self._thread_name_prefix or self
            )
            for t in self._threads:
                self._work_queue.put(None)
                t.join()
        logger.debug("shutdown finish %s", self._thread_name_prefix or self)

"""Explicit workstation runtime policy and bounded background execution."""
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore


@dataclass(frozen=True)
class RuntimeLimits:
    upload_bytes: int = 100 * 1024 * 1024
    worker_output_bytes: int = 100 * 1024 * 1024
    worker_seconds: int = 90
    distribution_elements: int = 100_000
    port_relations: int = 1_000_000
    assignment_cells: int = 2_000_000


LIMITS = RuntimeLimits()


def startup_policy(environ):
    """No network exposure or example downloads without an explicit opt-in."""
    return dict(share=environ.get('IT2_SHARE') == '1',
                download_models=environ.get('IT2_DOWNLOAD_MODELS') == '1',
                public_demo=environ.get('IT2_PUBLIC_DEMO') == '1')


class BoundedExecutor:
    """One running experiment, no unbounded queued jobs across browser sessions."""
    def __init__(self):
        self._slot = BoundedSemaphore(1)
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='it2-experiment')

    def submit(self, function, *args, **kwargs):
        if not self._slot.acquire(blocking=False):
            raise ValueError('An experiment is already running on this host. Wait for it to finish before starting another.')
        def run():
            try:
                return function(*args, **kwargs)
            finally:
                self._slot.release()
        try:
            return self._pool.submit(run)
        except BaseException:
            self._slot.release()
            raise

    def shutdown(self):
        self._pool.shutdown(wait=True)

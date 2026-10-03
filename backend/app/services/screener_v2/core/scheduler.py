"""Local recurring screen execution, sharing the existing durable job runner."""
import logging
import threading
from .state import claim_due_schedules, get_screen, schedule_result

logger = logging.getLogger(__name__)


class ScreenScheduler:
    def __init__(self, submit):
        self.submit = submit
        self.stop_event = threading.Event()
        self.thread = None

    def tick(self, now=None):
        for due in claim_due_schedules(now):
            screen_id = due['screen_id']
            try:
                definition = get_screen(screen_id)
                payload = {**definition['payload'], 'screen_id': screen_id}
                job = self.submit(definition['feature_id'], payload, f'schedule:{screen_id}:{due["due"]}')
                schedule_result(screen_id, job_id=job['job_id'])
            except (KeyError, TypeError, ValueError, OSError, RuntimeError) as exc:
                # A failed dispatch is persisted and logged, never published as a result.
                logger.exception('Screener schedule dispatch failed for %s', screen_id)
                schedule_result(screen_id, error=f'{type(exc).__name__}: {exc}')

    def _run(self):
        while not self.stop_event.is_set():
            self.tick()
            self.stop_event.wait(30)

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, name='screener-scheduler', daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=1)

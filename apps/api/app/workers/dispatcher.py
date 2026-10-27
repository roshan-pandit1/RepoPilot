import logging
import time
from datetime import timedelta

from sqlalchemy import select

from app.domain.models import Outbox, now
from app.infra.database import get_session_factory
from app.workers.tasks import ingest_issue

logger = logging.getLogger("repopilot.dispatcher")


def dispatch_once(factory=None, publish=None):
    factory = factory or get_session_factory()
    publish = publish or (lambda event_id: ingest_issue.apply_async(
        args=[event_id], task_id=event_id, retry=False))
    with factory.begin() as db:
        events = db.scalars(select(Outbox).where(
            Outbox.status == "pending", Outbox.next_dispatch_at <= now()
        ).order_by(Outbox.next_dispatch_at).limit(50).with_for_update(skip_locked=True))
        for event in events:
            if event.attempts >= 20:
                event.status = "failed"
                continue
            event.attempts += 1
            event.next_dispatch_at = now() + timedelta(seconds=min(300, 2 ** event.attempts))
            try:
                publish(event.id)
            except Exception:
                logger.warning("outbox_publish_failed")
            # Remains pending until worker commits. Republish also repairs broker loss.


def main():
    logging.basicConfig(level=logging.INFO,
                        format='{"level":"%(levelname)s","event":"%(message)s"}')
    while True:
        try:
            dispatch_once()
        except Exception:
            logger.error("outbox_dispatch_failed")
        time.sleep(2)


if __name__ == "__main__":
    main()

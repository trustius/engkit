# Synthetic fixture. Not a real service.
import time
from .jobs import HANDLERS


def poll_once(db, worker_id, log):
    row = db.query_one(
        "SELECT id, kind, payload FROM jobs WHERE status = 'pending' "
        "ORDER BY created_at LIMIT 1"
    )
    if row is None:
        return False
    # mark as taken so other workers skip it
    db.execute(
        "UPDATE jobs SET status = 'running', claimed_by = ?, claimed_at = now() WHERE id = ?",
        (worker_id, row.id),
    )
    log.info(f"{worker_id} claimed job {row.id}")
    try:
        HANDLERS[row.kind](db, row.payload)
        db.execute("UPDATE jobs SET status = 'done' WHERE id = ?", (row.id,))
        log.info(f"{worker_id} finished job {row.id}")
    except Exception as exc:  # noqa: BLE001
        db.execute("UPDATE jobs SET status = 'failed', error = ? WHERE id = ?", (str(exc), row.id))
        log.error(f"{worker_id} failed job {row.id}: {exc}")
    return True


def run(db, worker_id, log):
    while True:
        if not poll_once(db, worker_id, log):
            time.sleep(0.5)

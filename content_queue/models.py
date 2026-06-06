QUEUE_STATUSES = ("draft", "scheduled", "processing", "posted", "failed")


def normalize_queue_status(status: str) -> str:
    normalized = (status or "draft").strip().lower()
    if normalized not in QUEUE_STATUSES:
        return "draft"
    return normalized

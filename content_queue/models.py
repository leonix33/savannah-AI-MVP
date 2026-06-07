QUEUE_STATUSES = ("queued", "scheduled", "publishing", "posted", "failed")


def normalize_queue_status(status: str) -> str:
    normalized = (status or "draft").strip().lower()
    if normalized in ("draft", "processing"):
        return "queued" if normalized == "draft" else "publishing"
    if normalized not in QUEUE_STATUSES:
        return "queued"
    return normalized

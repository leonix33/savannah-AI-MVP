def schedule_post_placeholder(queue_item_id: int, scheduled_time: str) -> dict:
    return {
        "queue_item_id": queue_item_id,
        "scheduled_time": scheduled_time,
        "status": "scheduled",
        "message": "Post marked as scheduled locally. No external platform call was made.",
    }

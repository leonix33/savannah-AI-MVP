from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from facebook_publisher import mark_post_posted, publish_post
from utils import db


def _scheduled_datetime(post: dict):
    scheduled_date = post.get("scheduled_date")
    scheduled_time = post.get("scheduled_time")
    timezone = post.get("timezone") or "America/New_York"
    if not scheduled_date or not scheduled_time:
        return None

    try:
        return datetime.fromisoformat(f"{scheduled_date}T{scheduled_time}").replace(tzinfo=ZoneInfo(timezone))
    except (TypeError, ValueError, ZoneInfoNotFoundError):
        return None


def _is_ready_for_publish(post: dict, now: datetime | None = None) -> bool:
    scheduled_at = _scheduled_datetime(post)
    if not scheduled_at:
        return False
    current_time = now or datetime.now(scheduled_at.tzinfo)
    return scheduled_at <= current_time


def scan_queued_posts() -> list[dict]:
    rows = db.list_scheduled_queue_items(200)
    posts = []
    for row in rows:
        posts.append(
            {
                "id": row[0],
                "platform": row[1],
                "tone": row[2],
                "content": row[3],
                "hashtags": row[4],
                "media_type": row[5],
                "media_name": row[6],
                "status": row[7],
                "scheduled_date": row[8],
                "scheduled_time": row[9],
                "timezone": row[10],
                "created_at": row[11],
            }
        )
    return posts


def run_scheduler_worker(simulate_only: bool = True) -> dict:
    posts = scan_queued_posts()
    ready_posts = [post for post in posts if post["status"] == "scheduled" and _is_ready_for_publish(post)]
    results = []

    for post in ready_posts:
        queue_id = post["id"]
        platform = post.get("platform") or "Unknown"
        try:
            db.update_queue_status(queue_id, "publishing")
            publish_result = publish_post(post)
            if publish_result["success"]:
                mark_post_posted(queue_id, platform, publish_result["message"])
                results.append({"queue_item_id": queue_id, "status": "posted", "message": publish_result["message"]})
            else:
                db.update_queue_status(queue_id, "failed")
                db.add_publishing_log(
                    queue_item_id=queue_id,
                    platform=platform,
                    status="failed",
                    message=publish_result["message"],
                    error_message=publish_result["message"],
                )
                results.append({"queue_item_id": queue_id, "status": "failed", "message": publish_result["message"]})
        except (KeyError, RuntimeError, ValueError) as exc:
            db.update_queue_status(queue_id, "failed")
            db.add_publishing_log(
                queue_item_id=queue_id,
                platform=platform,
                status="failed",
                message="Scheduler worker failed.",
                error_message=str(exc),
            )
            results.append({"queue_item_id": queue_id, "status": "failed", "message": str(exc)})

    return {
        "simulate_only": simulate_only,
        "scanned": len(posts),
        "ready": len(ready_posts),
        "results": results,
    }

from datetime import datetime

from utils import db


PLATFORM_RECOMMENDED_TIMES = {
    "Facebook": "18:00",
    "Instagram": "12:00",
    "TikTok": "20:00",
}


def recommend_time_for_platform(platform: str) -> str:
    return PLATFORM_RECOMMENDED_TIMES.get(platform or "", "18:00")


def detect_scheduled_posts(limit: int = 100) -> list[dict]:
    rows = db.list_scheduled_queue_items(limit)
    return [
        {
            "id": row[0],
            "platform": row[1],
            "tone": row[2],
            "caption": row[3],
            "hashtags": row[4],
            "media_type": row[5],
            "media_name": row[6],
            "status": row[7],
            "scheduled_date": row[8],
            "scheduled_time": row[9],
            "timezone": row[10],
            "created_at": row[11],
        }
        for row in rows
    ]


def simulate_scheduler_run() -> dict:
    scheduled_posts = detect_scheduled_posts()
    return {
        "checked_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "scheduled_count": len([post for post in scheduled_posts if post["status"] == "scheduled"]),
        "publishing_count": len([post for post in scheduled_posts if post["status"] == "publishing"]),
        "message": "Scheduler simulation only. No post was published.",
    }

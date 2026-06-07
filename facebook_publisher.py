from config import settings
from utils import db


def validate_post(post: dict) -> tuple[bool, str]:
    content = (post.get("content") or post.get("caption") or "").strip()
    platform = (post.get("platform") or "").strip()

    if not content:
        return False, "Post content is required."
    if not platform:
        return False, "Platform is required."
    if platform.lower() != "facebook":
        return True, "Non-Facebook post is valid for simulation."
    if not settings.AUTO_PUBLISH_MODE:
        return True, "Facebook post is valid for simulated publishing."
    if not settings.FACEBOOK_PAGE_ID or not settings.FACEBOOK_PAGE_ACCESS_TOKEN:
        return False, "Facebook page settings are missing."
    return True, "Post is valid."


def simulate_publish(post: dict) -> dict:
    return {
        "success": True,
        "mode": "simulation",
        "platform": post.get("platform", "Facebook"),
        "message": "Simulated publish completed. No Meta API call was made.",
    }


def publish_post(post: dict) -> dict:
    is_valid, validation_message = validate_post(post)
    if not is_valid:
        return {
            "success": False,
            "mode": "validation",
            "platform": post.get("platform", "Unknown"),
            "message": validation_message,
        }

    if not settings.AUTO_PUBLISH_MODE:
        return simulate_publish(post)

    # Future Meta Graph API integration placeholder:
    # 1. Use FACEBOOK_PAGE_ID and FACEBOOK_PAGE_ACCESS_TOKEN from secure settings.
    # 2. Upload media if media_type is image/video.
    # 3. Create the page post with caption/content.
    # 4. Store the Meta post id in a publishing log or queue metadata table.
    return {
        "success": False,
        "mode": "placeholder",
        "platform": post.get("platform", "Facebook"),
        "message": "AUTO_PUBLISH_MODE is enabled, but real Meta publishing is not implemented yet.",
    }


def mark_post_posted(queue_item_id: int, platform: str, message: str = "") -> None:
    db.update_queue_status(queue_item_id, "posted")
    db.add_publishing_log(
        queue_item_id=queue_item_id,
        platform=platform,
        status="posted",
        message=message or "Post marked as posted by publishing engine.",
    )

from config import settings


def validate_facebook_config() -> dict:
    missing = []
    if not settings.FACEBOOK_PAGE_ID:
        missing.append("FACEBOOK_PAGE_ID")
    if not settings.FACEBOOK_PAGE_ACCESS_TOKEN:
        missing.append("FACEBOOK_PAGE_ACCESS_TOKEN")

    return {
        "ready": not missing,
        "missing": missing,
        "message": (
            "Facebook configuration is present."
            if not missing
            else "Facebook publishing is not configured yet. Add required settings before real Meta API integration."
        ),
    }


def connect_facebook_page_placeholder() -> dict:
    validation = validate_facebook_config()
    return {
        "connected": False,
        "ready_for_future_integration": validation["ready"],
        "message": "Placeholder only. No Facebook or Meta API connection was attempted.",
        "config": validation,
    }


def publish_post_placeholder(caption: str, media_name: str | None = None) -> dict:
    return {
        "posted": False,
        "caption_preview": (caption or "")[:120],
        "media_name": media_name,
        "message": "Placeholder only. No post was published to Facebook.",
    }

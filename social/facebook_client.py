from config import settings


def _is_real_value(value: str) -> bool:
    # Placeholder text from .env.example (e.g. "your_..._here") does not count as configured.
    normalized = (value or "").strip().lower()
    if not normalized:
        return False
    return not any(marker in normalized for marker in ("paste_", "your_", "_here"))


def validate_facebook_page_config() -> dict:
    missing = []
    if not _is_real_value(settings.FACEBOOK_PAGE_ID):
        missing.append("FACEBOOK_PAGE_ID")
    if not _is_real_value(settings.FACEBOOK_PAGE_ACCESS_TOKEN):
        missing.append("FACEBOOK_PAGE_ACCESS_TOKEN")

    return {
        "ready": not missing,
        "missing": missing,
        "message": (
            "Facebook Page config is present. Live publishing remains disabled."
            if not missing
            else f"Facebook Page config incomplete. Missing: {', '.join(missing)}."
        ),
    }


def get_facebook_connection_status() -> dict:
    validation = validate_facebook_page_config()
    live_publishing = settings.LIVE_SOCIAL_PUBLISHING

    if validation["ready"]:
        status = "Configured (not connected)"
        message = "Facebook Page settings detected. No Meta API connection has been made."
    else:
        status = "Not configured"
        message = validation["message"]

    return {
        "platform": "Facebook",
        "status": status,
        "configured": validation["ready"],
        "live_publishing": live_publishing,
        "mode": "Live Publishing Enabled" if live_publishing else "Safe Demo Mode / Live Publishing Disabled",
        "message": message,
    }


def get_instagram_connection_status() -> dict:
    configured = _is_real_value(settings.INSTAGRAM_BUSINESS_ID)
    return {
        "platform": "Instagram",
        "status": "Configured (not connected)" if configured else "Not configured",
        "configured": configured,
        "message": (
            "Instagram Business ID detected. No API connection has been made."
            if configured
            else "INSTAGRAM_BUSINESS_ID is not set. Instagram publishing is a future step."
        ),
    }


def get_tiktok_connection_status() -> dict:
    configured = _is_real_value(settings.TIKTOK_BUSINESS_ID)
    return {
        "platform": "TikTok",
        "status": "Configured (not connected)" if configured else "Not configured",
        "configured": configured,
        "message": (
            "TikTok Business ID detected. No API connection has been made."
            if configured
            else "TIKTOK_BUSINESS_ID is not set. TikTok publishing is a future step."
        ),
    }


def publish_facebook_post_placeholder(caption: str, media_name: str | None = None) -> dict:
    caption_text = (caption or "").strip()
    if not caption_text:
        return {
            "posted": False,
            "simulated": False,
            "message": "No content available to simulate. Generate or queue a post first.",
        }

    if not settings.LIVE_SOCIAL_PUBLISHING:
        # Future Meta Graph API integration would go here, gated behind LIVE_SOCIAL_PUBLISHING.
        return {
            "posted": False,
            "simulated": True,
            "caption_preview": caption_text[:120],
            "media_name": media_name,
            "message": "Simulated Facebook publish. LIVE_SOCIAL_PUBLISHING is false, so no Meta API call was made.",
        }

    return {
        "posted": False,
        "simulated": True,
        "caption_preview": caption_text[:120],
        "media_name": media_name,
        "message": "LIVE_SOCIAL_PUBLISHING is enabled, but real Meta publishing is not implemented yet. Simulation only.",
    }


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

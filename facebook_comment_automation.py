from config import settings


def classify_comment(comment_text: str) -> str:
    text = (comment_text or "").lower()
    if any(word in text for word in ("price", "cost", "how much", "$", "menu")):
        return "sales_question"
    if any(word in text for word in ("where", "location", "address", "open", "hours", "when")):
        return "location_or_hours"
    if any(word in text for word in ("cater", "party", "event", "wedding", "office")):
        return "catering_lead"
    if any(word in text for word in ("love", "great", "amazing", "best", "fire", "delicious")):
        return "positive_engagement"
    if any(word in text for word in ("bad", "cold", "wrong", "wait", "problem", "disappointed")):
        return "service_issue"
    return "general_engagement"


def generate_ai_reply(comment_text: str, classification: str, tone: str = "Friendly") -> str:
    base = (comment_text or "").strip()
    if classification == "catering_lead":
        return "Thanks for asking! We would love to help with catering. Send us a message with your date, guest count, and favorite BBQ items so we can help you plan it."
    if classification == "location_or_hours":
        return "Thanks for checking in! We will post our latest location and hours here. Send us a message if you need today's exact schedule."
    if classification == "sales_question":
        return "Great question! Send us a message with what you are craving and we can help with menu options, pricing, and the best BBQ combo for you."
    if classification == "positive_engagement":
        return "Thank you so much! We appreciate the love and cannot wait to serve you more smoky, fresh BBQ soon."
    if classification == "service_issue":
        return "Thank you for letting us know. We want every order to be right. Please message us with the details so we can look into it and make it better."
    if base:
        return f"Thanks for reaching out! We appreciate you commenting and hope to serve you soon. {tone} BBQ energy all day."
    return "Thanks for reaching out! We appreciate the support and hope to serve you soon."


def validate_reply(comment: dict, reply_text: str) -> tuple[bool, str]:
    if not (comment.get("comment_text") or "").strip():
        return False, "Original comment is required."
    if not (reply_text or "").strip():
        return False, "Reply text is required."
    return True, "Reply is ready for simulated publishing."


def simulate_reply_publish(comment: dict, reply_text: str) -> dict:
    commenter = comment.get("commenter_name") or "Facebook user"
    reply_preview = (reply_text or "").strip()[:80]
    return {
        "success": True,
        "mode": "simulation",
        "message": f"Simulated Facebook reply to {commenter}: {reply_preview}. No real Facebook comment was posted.",
    }


def publish_comment_reply(comment: dict, reply_text: str) -> dict:
    is_valid, validation_message = validate_reply(comment, reply_text)
    if not is_valid:
        return {"success": False, "mode": "validation", "message": validation_message}

    if not getattr(settings, "LIVE_FACEBOOK_MODE", False):
        return simulate_reply_publish(comment, reply_text)

    # Future Meta Graph API placeholder:
    # 1. Read the Facebook comment id from comment metadata.
    # 2. POST the approved reply to /{comment-id}/comments with a Page access token.
    # 3. Save the returned Meta reply id and timestamp.
    return {
        "success": False,
        "mode": "placeholder",
        "message": "LIVE_FACEBOOK_MODE is enabled, but real Facebook replies are not implemented yet.",
    }

import requests

from config import settings


GRAPH_BASE_URL = f"https://graph.facebook.com/{settings.FACEBOOK_GRAPH_VERSION}"


def is_real_meta_value(value: str) -> bool:
    normalized = (value or "").strip().lower()
    if not normalized:
        return False
    return not any(marker in normalized for marker in ("paste_", "your_", "_here"))


def validate_facebook_graph_config() -> tuple[bool, str]:
    if not is_real_meta_value(settings.FACEBOOK_PAGE_ID):
        return False, "FACEBOOK_PAGE_ID is missing."
    if not is_real_meta_value(settings.FACEBOOK_PAGE_ACCESS_TOKEN):
        return False, "FACEBOOK_PAGE_ACCESS_TOKEN is missing."
    return True, "Facebook Graph config is ready for read-only testing."


def _graph_get(path: str, params: dict | None = None) -> dict:
    request_params = dict(params or {})
    request_params["access_token"] = settings.FACEBOOK_PAGE_ACCESS_TOKEN
    response = requests.get(f"{GRAPH_BASE_URL}/{path.lstrip('/')}", params=request_params, timeout=20)
    payload = response.json()
    if response.status_code >= 400:
        error = payload.get("error", {})
        message = error.get("message") or "Facebook Graph API request failed."
        raise RuntimeError(message)
    return payload


def fetch_recent_page_comments(post_limit: int = 5, comments_per_post: int = 10) -> dict:
    is_valid, message = validate_facebook_graph_config()
    if not is_valid:
        return {"success": False, "message": message, "comments": []}

    fields = f"id,message,created_time,comments.limit({comments_per_post}){{id,message,from,created_time}}"
    try:
        payload = _graph_get(
            f"{settings.FACEBOOK_PAGE_ID}/posts",
            {"fields": fields, "limit": post_limit},
        )
    except (RuntimeError, requests.RequestException, ValueError) as exc:
        return {"success": False, "message": str(exc), "comments": []}

    comments = []
    for post in payload.get("data", []):
        post_id = post.get("id", "")
        post_message = post.get("message") or "Facebook Page post"
        for comment in post.get("comments", {}).get("data", []):
            commenter = comment.get("from", {}) or {}
            comments.append(
                {
                    "facebook_post_id": post_id,
                    "source_post": post_message[:120],
                    "facebook_comment_id": comment.get("id", ""),
                    "commenter_name": commenter.get("name", "Facebook user"),
                    "comment_text": comment.get("message", ""),
                    "created_time": comment.get("created_time", ""),
                }
            )

    return {
        "success": True,
        "message": f"Fetched {len(comments)} comment(s) in read-only mode.",
        "comments": comments,
    }

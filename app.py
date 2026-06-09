import os
import io
import csv
import html
import base64
import tempfile
import re
from collections import Counter
from datetime import date, datetime, time
from dotenv import load_dotenv
import streamlit as st
import streamlit.components.v1 as components
import openai
from PIL import Image, ImageOps
from utils import db
from social.facebook_client import validate_facebook_config
from scheduler.runner import recommend_time_for_platform, simulate_scheduler_run
from scheduler_worker import run_scheduler_worker
from config import settings
from facebook_comment_automation import classify_comment, generate_ai_reply, publish_comment_reply
from social.facebook_graph_client import fetch_recent_page_comments, is_real_meta_value, validate_facebook_graph_config

load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")
TEXT_MODEL = os.environ.get("OPENAI_TEXT_MODEL", "gpt-3.5-turbo")
VISION_MODEL = os.environ.get("OPENAI_VISION_MODEL", "gpt-4o-mini")
MAX_IMAGE_SIDE = int(os.environ.get("MAX_IMAGE_SIDE", "1024"))
IMAGE_JPEG_QUALITY = int(os.environ.get("IMAGE_JPEG_QUALITY", "82"))
MAX_VIDEO_SECONDS = int(os.environ.get("MAX_VIDEO_SECONDS", "30"))
MAX_VIDEO_UPLOAD_MB = int(os.environ.get("MAX_VIDEO_UPLOAD_MB", "50"))
VIDEO_FRAME_COUNT = int(os.environ.get("VIDEO_FRAME_COUNT", "3"))

PLATFORM_CAMPAIGN_GUIDANCE = {
    "Facebook": (
        "Write for a Facebook business Page. Use a community-focused, family/local business tone. "
        "Use slightly longer captions, invite conversation, and include one engagement question."
    ),
    "Instagram": (
        "Write for Instagram. Use visual storytelling, food-focused emotional language, and a polished aesthetic tone. "
        "Keep hashtags clean, relevant, and easy to scan."
    ),
    "TikTok": (
        "Write for TikTok. Lead with a strong opening hook, keep copy punchy, and make it feel trend-aware. "
        "Use short lines, high energy, and a clear action."
    ),
}

CAMPAIGN_GOALS = [
    "Drive catering leads",
    "Increase weekend traffic",
    "Promote late-night food",
    "Increase delivery orders",
]
TARGET_AUDIENCES = [
    "Families",
    "College students",
    "BBQ lovers",
    "Event guests",
    "Nightlife crowd",
]
PROMOTION_TYPES = [
    "Weekend special",
    "Catering",
    "Event",
    "Delivery promo",
    "Limited-time special",
]


def apply_demo_styles():
    st.markdown(
        """
        <style>
        .stApp {
            background: radial-gradient(circle at top left, rgba(249, 115, 22, 0.16), transparent 28%),
                        linear-gradient(180deg, #0b0f14 0%, #14110f 100%);
            color: #f8fafc;
        }
        [data-testid="stHeader"] {
            background: rgba(11, 15, 20, 0.75);
        }
        .block-container {
            padding-top: 2rem;
            padding-bottom: 4rem;
            max-width: 1120px;
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #11100f 0%, #1a1410 100%);
        }
        [data-testid="stSidebar"] * {
            color: #f8efe5;
        }
        h1, h2, h3 {
            letter-spacing: -0.03em;
        }
        div[data-testid="stTabs"] button {
            padding: 0.7rem 0.9rem;
            border-radius: 999px;
            font-weight: 700;
        }
        div[data-testid="stTabs"] div[role="tablist"] {
            gap: 0.35rem;
            flex-wrap: wrap;
        }
        div[data-testid="stTabs"] button[aria-selected="true"] {
            background: #f97316;
            color: #111827;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: rgba(249, 115, 22, 0.22) !important;
            background: rgba(15, 23, 42, 0.36);
            border-radius: 18px;
        }
        div[data-testid="stMetric"] {
            background: rgba(17, 24, 39, 0.04);
            border: 1px solid rgba(249, 115, 22, 0.18);
            border-radius: 18px;
            padding: 1rem;
        }
        .sbg-hero {
            border: 1px solid rgba(249, 115, 22, 0.22);
            border-radius: 28px;
            padding: 1.5rem;
            margin: 1rem 0 1.25rem;
            background: linear-gradient(135deg, rgba(17, 24, 39, 0.96), rgba(68, 32, 16, 0.94));
            color: #fff7ed;
            box-shadow: 0 18px 55px rgba(17, 24, 39, 0.18);
        }
        .sbg-eyebrow {
            color: #fdba74;
            text-transform: uppercase;
            font-weight: 800;
            letter-spacing: 0.12em;
            font-size: 0.78rem;
            margin-bottom: 0.4rem;
        }
        .sbg-hero h1 {
            margin: 0;
            font-size: clamp(2rem, 5vw, 3.6rem);
            line-height: 1.02;
        }
        .sbg-hero p {
            color: #fed7aa;
            font-size: 1.05rem;
            line-height: 1.65;
            max-width: 780px;
        }
        .sbg-chip {
            display: inline-flex;
            align-items: center;
            border: 1px solid rgba(253, 186, 116, 0.4);
            border-radius: 999px;
            padding: 0.32rem 0.7rem;
            margin: 0.18rem 0.22rem 0.18rem 0;
            color: #ffedd5;
            background: rgba(255,255,255,0.06);
            font-size: 0.82rem;
            font-weight: 700;
        }
        .sbg-card {
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 18px;
            padding: 1rem;
            margin: 0.75rem 0;
            background: rgba(255, 255, 255, 0.035);
        }
        .sbg-badge {
            display: inline-block;
            border-radius: 999px;
            padding: 0.25rem 0.65rem;
            font-size: 0.76rem;
            font-weight: 800;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }
        .sbg-badge-queued { background: #dbeafe; color: #1e3a8a; }
        .sbg-badge-scheduled { background: #fef3c7; color: #92400e; }
        .sbg-badge-publishing { background: #ede9fe; color: #5b21b6; }
        .sbg-badge-posted, .sbg-badge-approved, .sbg-badge-simulated_replied { background: #dcfce7; color: #166534; }
        .sbg-badge-failed { background: #fee2e2; color: #991b1b; }
        .sbg-badge-new, .sbg-badge-classified, .sbg-badge-reply_drafted { background: #e0f2fe; color: #075985; }
        .sbg-preview {
            white-space: pre-wrap;
            border-left: 3px solid #f97316;
            padding: 0.75rem 0.9rem;
            border-radius: 12px;
            background: rgba(249, 115, 22, 0.06);
            line-height: 1.6;
        }
        .sbg-muted {
            color: #78716c;
            font-size: 0.9rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def badge(label: str) -> str:
    safe_label = html.escape((label or "unknown").replace("_", " "))
    css_label = re.sub(r"[^a-z0-9_]+", "-", (label or "unknown").lower())
    return f'<span class="sbg-badge sbg-badge-{css_label}">{safe_label}</span>'


def toast_success(message: str):
    if hasattr(st, "toast"):
        st.toast(message)
    st.success(message)


def render_onboarding_helper():
    with st.expander("Demo Guide: How to Show This MVP", expanded=False):
        st.markdown(
            """
            **Quick demo path**

            1. Generate a platform-aware campaign for a brisket, delivery, or late-night special.
            2. Add the result to the Content Queue.
            3. Schedule it and review it on the Campaign Calendar.
            4. Open Analytics to show the business dashboard.
            5. Open Comment Automation, add demo comments, generate replies, approve, and simulate.

            **How Savannah BBQ uses it**

            The owner can plan weekly specials, queue social posts, review publishing readiness, handle Facebook comments,
            and track activity from one local dashboard while keeping real publishing disabled until ready.
            """
        )


def init_app():
    try:
        db.init_db()
    except Exception:
        pass


def load_prompt(filename: str, fallback: str = "") -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return fallback


def make_prompt(task: str, template: str, user_input: str, tone: str, platform: str, n: int) -> str:
    return template.format(
        task=task,
        input=user_input or "",
        tone=tone,
        platform=platform,
        n=n,
    )


def generate_content(prompt: str):
    try:
        response = openai.ChatCompletion.create(
            model=TEXT_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful, creative social media assistant for a local food truck."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
            max_tokens=500,
        )
        content = response["choices"][0]["message"]["content"].strip()
        usage = response.get("usage", {})
        return content, usage
    except Exception as exc:
        raise RuntimeError(f"OpenAI generation failed: {exc}") from exc


def optimize_image_for_vision(image_bytes: bytes) -> tuple[bytes, str]:
    image = Image.open(io.BytesIO(image_bytes))
    image = ImageOps.exif_transpose(image)
    image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))

    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=IMAGE_JPEG_QUALITY, optimize=True)
    return buffer.getvalue(), "image/jpeg"


def extract_video_frames_for_vision(video_bytes: bytes, suffix: str) -> tuple[list[bytes], float]:
    try:
        cv2 = __import__("cv2")
    except ImportError as exc:
        raise RuntimeError("Video support requires opencv-python-headless to be installed.") from exc

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(video_bytes)
        tmp_path = tmp.name

    capture = None
    try:
        capture = cv2.VideoCapture(tmp_path)
        if not capture.isOpened():
            raise RuntimeError("Could not read uploaded video.")

        fps = capture.get(cv2.CAP_PROP_FPS) or 0
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = frame_count / fps if fps else 0

        if duration and duration > MAX_VIDEO_SECONDS:
            raise RuntimeError(f"Video is {duration:.1f}s. Please upload a video {MAX_VIDEO_SECONDS}s or shorter.")

        if frame_count <= 0:
            raise RuntimeError("Could not find frames in uploaded video.")

        sample_count = max(1, min(VIDEO_FRAME_COUNT, frame_count))
        if sample_count == 1:
            frame_indices = [0]
        else:
            frame_indices = [
                round(i * (frame_count - 1) / (sample_count - 1))
                for i in range(sample_count)
            ]

        frames = []
        for frame_index in frame_indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = capture.read()
            if not ok:
                continue

            ok, encoded = cv2.imencode(".jpg", frame)
            if not ok:
                continue

            optimized_frame, _ = optimize_image_for_vision(encoded.tobytes())
            frames.append(optimized_frame)

        if not frames:
            raise RuntimeError("Could not extract usable frames from uploaded video.")

        return frames, duration
    finally:
        if capture is not None:
            capture.release()
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def generate_image_content(prompt: str, image_bytes: bytes, image_mime: str):
    image_data = base64.b64encode(image_bytes).decode("utf-8")
    image_url = f"data:{image_mime};base64,{image_data}"

    try:
        response = openai.ChatCompletion.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a visual marketing assistant for Savannah Smokes, "
                        "a local BBQ food truck. Write practical, social-ready copy "
                        "based on the uploaded food or event photo."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                },
            ],
            temperature=0.8,
            max_tokens=650,
        )
        content = response["choices"][0]["message"]["content"].strip()
        usage = response.get("usage", {})
        return content, usage
    except Exception as exc:
        raise RuntimeError(f"OpenAI image generation failed: {exc}") from exc


def generate_video_content(prompt: str, frames: list[bytes]):
    content = [{"type": "text", "text": prompt}]
    for frame in frames:
        image_data = base64.b64encode(frame).decode("utf-8")
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}})

    try:
        response = openai.ChatCompletion.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a video marketing assistant for Savannah Smokes, "
                        "a local BBQ food truck. Infer the short video from sampled frames "
                        "and write practical, social-ready restaurant marketing copy."
                    ),
                },
                {"role": "user", "content": content},
            ],
            temperature=0.8,
            max_tokens=650,
        )
        content_text = response["choices"][0]["message"]["content"].strip()
        usage = response.get("usage", {})
        return content_text, usage
    except Exception as exc:
        raise RuntimeError(f"OpenAI video generation failed: {exc}") from exc


def build_task_prompt(task: str, user_input: str, tone: str, platform: str, n: int) -> str:
    if task == "Campaign Generator":
        platform_guidance = PLATFORM_CAMPAIGN_GUIDANCE.get(
            platform,
            "Write platform-aware restaurant marketing copy that matches the selected channel and business goal.",
        )
        return (
            "You are the AI marketing strategist for Savannah Smokes, an AI Restaurant Marketing Operating System.\n\n"
            "Create platform-specific restaurant marketing campaign assets using this campaign brief:\n"
            f"{user_input}\n\n"
            f"Selected platform: {platform}\n"
            f"Tone: {tone}\n"
            f"Platform behavior: {platform_guidance}\n"
            f"Number of campaign variations: {n}\n\n"
            "For each variation, return exactly this structure:\n"
            "1. Promo angle\n"
            "2. Platform-specific caption\n"
            "3. Call-to-action\n"
            "4. Hashtags\n\n"
            "Make the campaign business-aware, useful for promoting sales, and specific to Savannah Smokes. "
            "Avoid generic captions that could belong to any restaurant."
        )

    if task == "Hashtag Generator":
        template = (
            "Generate {n} high-quality hashtags for {platform} posts about: {input}. "
            "Include a mix of local, food, BBQ, event, and engagement hashtags. "
            "Keep the hashtags clean, professional, and ready for social media. "
            "Return only hashtags separated by spaces or commas."
        )
        return make_prompt(
            task=task,
            template=template,
            user_input=user_input,
            tone=tone,
            platform=platform,
            n=n,
        )

    if task == "Image upload caption generator":
        template = (
            "Analyze the uploaded image and create {n} social media caption options for {platform}. "
            "Use a {tone} tone. Owner notes or campaign context: {input}. "
            "For each option, include a short caption, a clear call-to-action, and 5-8 relevant hashtags. "
            "Keep the copy accurate to what is visible in the image and avoid inventing details."
        )
        return make_prompt(
            task=task,
            template=template,
            user_input=user_input or "No extra notes provided.",
            tone=tone,
            platform=platform,
            n=n,
        )

    if task == "Video upload caption generator":
        template = (
            "Analyze the sampled frames from the uploaded short video and create {n} marketing options for {platform}. "
            "Use a {tone} tone. Owner notes or campaign context: {input}. "
            "For each option, include a strong opening hook, short caption, call-to-action, and 5-8 hashtags. "
            "If the platform is TikTok, make the hook especially punchy and trend-friendly. "
            "Do not claim motion or details that are not visible from the sampled frames."
        )
        return make_prompt(
            task=task,
            template=template,
            user_input=user_input or "No extra notes provided.",
            tone=tone,
            platform=platform,
            n=n,
        )

    if task == "Customer comment replies":
        template = load_prompt(
            "reply_prompt.txt",
            "You are a friendly customer reply assistant. Tone: {tone}. Customer comment: {input}. Write {n} thoughtful responses, numbered and concise.",
        )
    elif task == "Weekend promo post ideas":
        template = load_prompt(
            "promo_prompt.txt",
            "You are a promotional assistant for Savannah BBQ. Platform: {platform}. Tone: {tone}. Context: {input}. Generate {n} weekend promo post ideas with title, description, CTA, and hashtags.",
        )
    elif task == "Event announcements":
        template = load_prompt(
            "event_prompt.txt",
            "You are an event announcement writer for Savannah BBQ. Platform: {platform}. Tone: {tone}. Event details: {input}. Generate {n} engaging event announcement ideas with title and short copy.",
        )
    elif task == "Catering promotions":
        template = load_prompt(
            "catering_prompt.txt",
            "You are a catering promotion specialist for Savannah BBQ. Platform: {platform}. Tone: {tone}. Catering offer details: {input}. Generate {n} short promotional messages with benefits, CTA, and local appeal.",
        )
    elif task == "Email campaigns":
        template = load_prompt(
            "email_prompt.txt",
            "You are an email marketing writer for Savannah BBQ. Platform: {platform}. Tone: {tone}. Campaign description: {input}. Generate {n} email subject lines and body snippets for a short promotional email.",
        )
    else:
        template = load_prompt(
            "caption_prompt.txt",
            "You are a creative social copywriter for Savannah BBQ. Task: {task}. Platform: {platform}. Tone: {tone}. Description: {input}. Generate {n} short captions or hooks.",
        )

    return make_prompt(task=task, template=template, user_input=user_input, tone=tone, platform=platform, n=n)


def build_facebook_post_package(generation: dict) -> str:
    media_name = generation.get("media_name") or "No media attached"
    notes = generation.get("input") or "No extra notes provided."
    generated_copy = generation.get("result") or ""

    return "\n".join(
        [
            "Savannah Smokes Facebook Post Package",
            "",
            f"Status: Ready for owner review",
            f"Platform: Facebook Page",
            f"Source task: {generation.get('task', 'Unknown')}",
            f"Tone: {generation.get('tone', 'Unknown')}",
            f"Media: {media_name}",
            f"Owner notes: {notes}",
            "Suggested posting time: Today between 5:00 PM and 7:00 PM local time",
            "",
            "Caption / Hashtags:",
            generated_copy,
            "",
            "Next step: Review the copy, make edits if needed, then publish manually on Facebook.",
        ]
    )


def extract_hashtags(text: str) -> str:
    tags = re.findall(r"#\w+", text or "")
    return " ".join(dict.fromkeys(tags))


def infer_media_type(task: str, media_name: str | None) -> str:
    if task == "Image upload caption generator":
        return "image"
    if task == "Video upload caption generator":
        return "video"
    if media_name:
        return "media"
    return "text"


def parse_queue_date(value: str | None):
    if not value:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError:
        return date.today()


def parse_queue_time(value: str | None, platform: str | None = None):
    time_value = value or recommend_time_for_platform(platform or "")
    try:
        return time.fromisoformat(time_value)
    except ValueError:
        return time(18, 0)


def format_time_label(value: str | None) -> str:
    if not value:
        return "Unscheduled"
    try:
        return datetime.strptime(value, "%H:%M").strftime("%-I:%M %p")
    except ValueError:
        return value


def build_campaign_title(caption: str | None) -> str:
    first_line = (caption or "").strip().splitlines()[0] if (caption or "").strip() else "Untitled campaign"
    cleaned = re.sub(r"^[#*\-\d\.\s]+", "", first_line).strip()
    return cleaned[:80] or "Untitled campaign"


def render_content_queue():
    try:
        render_content_queue_body()
    except Exception as exc:
        st.subheader("Content Queue")
        st.warning("Content Queue is temporarily unavailable. Generation, copy, and download still work.")
        st.caption(str(exc))


def render_content_queue_body():
    st.subheader("Content Queue")
    st.caption("Edit, queue, schedule, and manage generated posts before future publishing automation.")

    if hasattr(db, "ensure_content_queue_table"):
        db.ensure_content_queue_table()

    latest_generation = st.session_state.get("latest_generation")
    latest_caption = (latest_generation or {}).get("result", "")

    # The composer lets the owner edit generated content before saving it to the queue.
    with st.container(border=True):
        st.markdown("**Queue composer**")
        if latest_generation:
            st.caption(
                f"Loaded from latest generation: {latest_generation.get('platform', 'Unknown platform')} | "
                f"{latest_generation.get('task', 'Unknown task')}"
            )
        else:
            st.caption("Paste content here, or generate content first to prefill this box.")

        draft_caption = st.text_area(
            "Edit content before queueing",
            value=latest_caption,
            height=220,
            key="queue_draft_caption",
            placeholder="Paste or edit a caption, hooks, hashtags, or campaign copy...",
        )
        composer_cols = st.columns([1, 1, 1])
        queue_platform = composer_cols[0].selectbox(
            "Platform",
            ["Facebook", "Instagram", "TikTok", "Threads", "LinkedIn", "General"],
            index=(
                ["Facebook", "Instagram", "TikTok", "Threads", "LinkedIn", "General"].index(
                    latest_generation.get("platform")
                )
                if latest_generation and latest_generation.get("platform") in ["Facebook", "Instagram", "TikTok", "Threads", "LinkedIn", "General"]
                else 0
            ),
            key="queue_draft_platform",
        )
        queue_tone = composer_cols[1].selectbox(
            "Tone",
            ["Friendly", "Playful", "Bold", "Professional", "Authentic Southern", "Urgent"],
            index=(
                ["Friendly", "Playful", "Bold", "Professional", "Authentic Southern", "Urgent"].index(
                    latest_generation.get("tone")
                )
                if latest_generation and latest_generation.get("tone") in ["Friendly", "Playful", "Bold", "Professional", "Authentic Southern", "Urgent"]
                else 0
            ),
            key="queue_draft_tone",
        )
        queue_media_type = composer_cols[2].selectbox(
            "Media type",
            ["text", "image", "video", "media"],
            index=0,
            key="queue_draft_media_type",
        )

        if st.button("Add to Queue"):
            if not draft_caption.strip():
                st.warning("Add content before queueing.")
                return
            if not hasattr(db, "add_queue_item"):
                st.warning("Queue storage is not ready yet. Please refresh after deployment finishes.")
                return

            with st.spinner("Adding post to the queue..."):
                media_name = latest_generation.get("media_name") if latest_generation else None
                media_type = infer_media_type(latest_generation.get("task") or "", media_name) if latest_generation else queue_media_type
                queue_id = db.add_queue_item(
                    platform=queue_platform,
                    content=draft_caption,
                    hashtags=extract_hashtags(draft_caption),
                    tone=queue_tone,
                    media_type=media_type,
                    media_name=media_name,
                    status="queued",
                )
            toast_success(f"Added queued post #{queue_id}.")
            st.rerun()

    if not hasattr(db, "list_queue_items"):
        st.info("Queue storage is still initializing. Refresh shortly to view queued posts.")
        return

    rows = db.list_queue_items(100)
    render_campaign_calendar(rows)
    render_publishing_logs()

    st.markdown("#### Queued posts")
    if not rows:
        st.write("No queued posts yet.")
        return

    status_options = ["queued", "scheduled", "publishing", "posted", "failed"]
    timezone_options = ["America/New_York", "America/Chicago", "America/Los_Angeles", "UTC"]

    for (
        queue_id,
        platform,
        tone,
        caption,
        hashtags,
        media_type,
        media_name,
        status,
        scheduled_date,
        scheduled_time,
        timezone,
        created_at,
    ) in rows:
        with st.container(border=True):
            header_cols = st.columns([3, 1, 1])
            header_cols[0].markdown(f"**{platform or 'General'}**")
            header_cols[0].caption(
                f"ID {queue_id} | Tone: {tone or 'Not set'} | {media_type or 'text'} | {media_name or 'No media'}"
            )
            header_cols[1].markdown(badge(status or "queued"), unsafe_allow_html=True)
            schedule_label = (
                f"{format_time_label(scheduled_time)} on {scheduled_date}"
                if scheduled_date or scheduled_time
                else "Not scheduled"
            )
            header_cols[2].caption(f"Created: {created_at}")
            header_cols[2].caption(f"Schedule: {schedule_label}")

            selected_status = st.selectbox(
                "Status",
                status_options,
                index=status_options.index(status) if status in status_options else 0,
                key=f"queue_status_{queue_id}",
            )
            selected_timezone = st.selectbox(
                "Timezone",
                timezone_options,
                index=timezone_options.index(timezone) if timezone in timezone_options else 0,
                key=f"queue_timezone_{queue_id}",
            )

            schedule_cols = st.columns([1, 1, 1, 1])
            selected_date = schedule_cols[0].date_input(
                "Date",
                value=parse_queue_date(scheduled_date),
                key=f"queue_date_{queue_id}",
            )
            selected_time = schedule_cols[1].time_input(
                "Time",
                value=parse_queue_time(scheduled_time, platform),
                key=f"queue_time_{queue_id}",
            )

            if schedule_cols[2].button("Schedule Post", key=f"queue_schedule_{queue_id}"):
                if not hasattr(db, "update_queue_status"):
                    st.warning("Queue scheduling is not ready yet. Please refresh after deployment finishes.")
                    return
                with st.spinner("Scheduling post..."):
                    db.update_queue_status(
                        queue_id,
                        "scheduled",
                        selected_date.isoformat(),
                        selected_time.strftime("%H:%M"),
                        selected_timezone,
                    )
                toast_success("Queued post marked as scheduled.")
                st.rerun()

            if schedule_cols[3].button("Update Status", key=f"queue_status_update_{queue_id}"):
                if not hasattr(db, "update_queue_status"):
                    st.warning("Queue status updates are not ready yet. Please refresh after deployment finishes.")
                    return
                with st.spinner("Updating queue status..."):
                    db.update_queue_status(
                        queue_id,
                        selected_status,
                        selected_date.isoformat() if selected_status != "queued" else scheduled_date,
                        selected_time.strftime("%H:%M") if selected_status != "queued" else scheduled_time,
                        selected_timezone,
                    )
                toast_success("Queued post status updated.")
                st.rerun()

            caption_preview = (caption or "").strip()
            if len(caption_preview) > 700:
                caption_preview = f"{caption_preview[:700]}..."

            # Each queued item can be edited inline without leaving the queue workflow.
            edit_key = f"queue_editing_{queue_id}"
            if st.session_state.get(edit_key):
                edited_caption = st.text_area(
                    "Edit queued content",
                    value=caption or "",
                    height=220,
                    key=f"queue_edit_text_{queue_id}",
                )
                edit_cols = st.columns(2)
                if edit_cols[0].button("Save Edit", key=f"queue_save_edit_{queue_id}"):
                    if not hasattr(db, "update_queue_item_caption"):
                        st.warning("Queue editing is not ready yet. Please refresh after deployment finishes.")
                        return
                    with st.spinner("Saving edit..."):
                        db.update_queue_item_caption(queue_id, edited_caption, extract_hashtags(edited_caption))
                    st.session_state[edit_key] = False
                    toast_success("Queued post updated.")
                    st.rerun()
                if edit_cols[1].button("Cancel Edit", key=f"queue_cancel_edit_{queue_id}"):
                    st.session_state[edit_key] = False
                    st.rerun()
            else:
                st.markdown("**Content preview**")
                st.markdown(
                    f'<div class="sbg-preview">{html.escape(caption_preview) if caption_preview else "No caption saved."}</div>',
                    unsafe_allow_html=True,
                )

            if hashtags:
                st.caption(f"Hashtags: {hashtags}")

            action_cols = st.columns(3)
            if action_cols[0].button("Edit", key=f"queue_edit_{queue_id}"):
                st.session_state[edit_key] = True
                st.rerun()
            if action_cols[1].button("Schedule", key=f"queue_schedule_shortcut_{queue_id}"):
                if not hasattr(db, "update_queue_status"):
                    st.warning("Queue scheduling is not ready yet. Please refresh after deployment finishes.")
                    return
                with st.spinner("Scheduling post..."):
                    db.update_queue_status(
                        queue_id,
                        "scheduled",
                        selected_date.isoformat(),
                        selected_time.strftime("%H:%M"),
                        selected_timezone,
                    )
                toast_success("Queued post scheduled.")
                st.rerun()
            if action_cols[2].button("Remove", key=f"queue_delete_{queue_id}"):
                if not hasattr(db, "delete_queue_item"):
                    st.warning("Queue deletion is not ready yet. Please refresh after deployment finishes.")
                    return
                with st.spinner("Removing queued post..."):
                    db.delete_queue_item(queue_id)
                toast_success("Removed queued post.")
                st.rerun()


def render_campaign_calendar(rows):
    st.markdown("#### Campaign Calendar")
    if not rows:
        st.write("Schedule queued posts to see them on the campaign calendar.")
        return

    scheduled_rows = [row for row in rows if row[7] in ("scheduled", "publishing", "posted", "failed")]
    if not scheduled_rows:
        st.write("No scheduled campaign posts yet.")
        return

    simulation = simulate_scheduler_run()
    st.caption(f"{simulation['message']} Scheduled posts detected: {simulation['scheduled_count']}.")

    for row in sorted(scheduled_rows, key=lambda item: (item[8] or "9999-12-31", item[9] or "99:99")):
        queue_id, platform, _tone, caption, _hashtags, _media_type, _media_name, status, scheduled_date, scheduled_time, timezone, _created_at = row
        try:
            day_label = date.fromisoformat(scheduled_date).strftime("%A")
        except (TypeError, ValueError):
            day_label = "Unscheduled day"

        calendar_cols = st.columns([1, 1, 2.2, 1, 1])
        calendar_cols[0].markdown(f"**{day_label}**")
        calendar_cols[1].write(platform or "General")
        calendar_cols[2].write(build_campaign_title(caption))
        calendar_cols[3].write(format_time_label(scheduled_time))
        calendar_cols[4].markdown(badge(status or "scheduled"), unsafe_allow_html=True)
        calendar_cols[4].caption(f"{timezone or 'America/New_York'} | #{queue_id}")


def render_publishing_logs():
    st.markdown("#### Publishing Log")
    run_cols = st.columns([1, 3])
    if run_cols[0].button("Run Scheduler Simulation"):
        with st.spinner("Running scheduler simulation..."):
            result = run_scheduler_worker(simulate_only=True)
        toast_success(f"Scheduler scanned {result['scanned']} post(s). Ready to publish: {result['ready']}.")

    if not hasattr(db, "list_publishing_logs"):
        st.caption("Publishing logs are not ready yet.")
        return

    logs = db.list_publishing_logs(10)
    if not logs:
        st.write("No publish attempts yet.")
        return

    for log_id, queue_item_id, platform, status, message, error_message, created_at in logs:
        with st.container(border=True):
            cols = st.columns([1, 1, 1, 2])
            cols[0].markdown(f"**#{log_id}**")
            cols[1].write(platform or "Unknown")
            cols[2].markdown(badge(status or "unknown"), unsafe_allow_html=True)
            cols[3].caption(f"{created_at} | Queue item #{queue_item_id}")
            st.write(message or "_No message recorded._")
            if error_message:
                st.error(error_message)


def build_bar_chart_data(counts: dict) -> dict:
    return {
        "label": list(counts.keys()),
        "count": list(counts.values()),
    }


def render_analytics_dashboard():
    st.subheader("Analytics Dashboard")
    st.caption("Local performance snapshot from generated content, queue activity, publishing simulations, and comment automation.")

    if not hasattr(db, "get_analytics_summary"):
        st.warning("Analytics are still initializing. Refresh after deployment finishes.")
        return

    analytics = db.get_analytics_summary()

    st.markdown("#### Content & Publishing")
    post_cols = st.columns(4)
    post_cols[0].metric("Generated posts", analytics["total_generated_posts"])
    post_cols[1].metric("Queued posts", analytics["queued_posts"])
    post_cols[2].metric("Scheduled posts", analytics["scheduled_posts"])
    post_cols[3].metric("Simulated published", analytics["simulated_published_posts"])

    st.markdown("#### Comment Automation")
    comment_cols = st.columns(5)
    comment_cols[0].metric("Comments ingested", analytics["total_comments_ingested"])
    comment_cols[1].metric("Replies drafted", analytics["replies_drafted"])
    comment_cols[2].metric("Replies approved", analytics["replies_approved"])
    comment_cols[3].metric("Replies simulated posted", analytics["replies_simulated_posted"])
    comment_cols[4].metric("Needs review", analytics["comments_needing_human_review"])

    chart_cols = st.columns(2)
    with chart_cols[0]:
        with st.container(border=True):
            st.markdown("#### Queue Status")
            queue_status_counts = analytics["queue_status_counts"]
            if queue_status_counts:
                st.bar_chart(build_bar_chart_data(queue_status_counts), x="label", y="count")
            else:
                st.write("No queue activity yet.")

    with chart_cols[1]:
        with st.container(border=True):
            st.markdown("#### Comments By Category")
            comments_by_category = analytics["comments_by_category"]
            if comments_by_category:
                st.bar_chart(build_bar_chart_data(comments_by_category), x="label", y="count")
            else:
                st.write("No comments classified yet.")

    with st.container(border=True):
        st.markdown("#### Comment Workflow")
        comment_status_counts = analytics["comment_status_counts"]
        if comment_status_counts:
            st.bar_chart(build_bar_chart_data(comment_status_counts), x="label", y="count")
        else:
            st.write("No comment workflow activity yet.")

    if analytics["comments_needing_human_review"]:
        st.warning("Some comments need human review before reply simulation.")
    else:
        st.success("No comments currently flagged for human review.")


def render_facebook_comment_automation_center():
    st.subheader("Facebook Comment Automation Center")
    st.caption("Ingest, classify, draft, approve, and simulate Facebook comment replies. Real replies are off by default.")
    st.info(f"LIVE_FACEBOOK_MODE is {'ON' if settings.LIVE_FACEBOOK_MODE else 'OFF'} - replies are simulated while this is off.")
    st.markdown(
        """
        **Demo workflow:** Add a manual/demo comment → Classify → Generate Reply → Save/Edit Draft → Approve Reply → Simulate Reply.
        """
    )
    config_cols = st.columns(3)
    page_id_configured = is_real_meta_value(getattr(settings, "FACEBOOK_PAGE_ID", ""))
    token_configured = is_real_meta_value(getattr(settings, "FACEBOOK_PAGE_ACCESS_TOKEN", ""))
    config_cols[0].metric("Facebook Page ID", "Configured" if page_id_configured else "Missing")
    config_cols[1].metric("Page Access Token", "Configured" if token_configured else "Missing")
    config_cols[2].metric("Graph Version", getattr(settings, "FACEBOOK_GRAPH_VERSION", "v20.0"))
    st.caption("Token value is intentionally hidden and never printed in the UI.")
    demo_mode_active = not (page_id_configured and token_configured)
    if demo_mode_active:
        st.warning("Demo Mode Active - manual and demo comments are enabled. Real Meta fetching is disabled until Page ID and token are configured.")
    else:
        st.success("Meta read-only configuration detected. Real comment fetching is available, but replies remain simulated.")

    if hasattr(db, "ensure_facebook_comments_table"):
        db.ensure_facebook_comments_table()

    with st.container(border=True):
        st.markdown("**Read-only Meta test**")
        st.caption("Fetch real Facebook Page comments into the local inbox. This does not post replies.")
        is_ready, config_message = validate_facebook_graph_config()
        if is_ready:
            st.success(config_message)
        else:
            st.warning(config_message)
        fetch_cols = st.columns([1, 1, 2])
        post_limit = fetch_cols[0].number_input("Posts to scan", min_value=1, max_value=25, value=5, step=1)
        comments_per_post = fetch_cols[1].number_input("Comments per post", min_value=1, max_value=50, value=10, step=1)
        if demo_mode_active:
            fetch_cols[2].caption("Real Meta fetch is disabled in Demo Mode.")
        if fetch_cols[2].button("Fetch Page Comments Read-Only", disabled=demo_mode_active):
            with st.spinner("Fetching Facebook comments in read-only mode..."):
                result = fetch_recent_page_comments(int(post_limit), int(comments_per_post))
            if not result["success"]:
                st.error(result["message"])
            else:
                imported = 0
                with st.spinner("Importing comments into the local inbox..."):
                    for comment in result["comments"]:
                        db.add_facebook_comment(
                            source_post=comment["source_post"],
                            commenter_name=comment["commenter_name"],
                            comment_text=comment["comment_text"],
                            facebook_post_id=comment["facebook_post_id"],
                            facebook_comment_id=comment["facebook_comment_id"],
                        )
                        imported += 1
                toast_success(f"{result['message']} Imported {imported} comment(s) into SQLite.")
                st.rerun()

    with st.container(border=True):
        st.markdown("**Comment ingestion**")
        source_post = st.text_input(
            "Source post or campaign",
            value="Facebook weekend BBQ promo",
            key="comment_source_post",
        )
        commenter_name = st.text_input("Commenter name", value="Facebook customer", key="commenter_name")
        comment_text = st.text_area(
            "Facebook comment",
            height=120,
            placeholder="Example: Do you cater office lunches this Friday?",
            key="facebook_comment_text",
        )
        ingest_cols = st.columns(2)
        if ingest_cols[0].button("Add Comment"):
            if not comment_text.strip():
                st.warning("Add a comment before saving.")
            else:
                with st.spinner("Adding comment to the local inbox..."):
                    comment_id = db.add_facebook_comment(source_post, commenter_name, comment_text)
                toast_success(f"Added comment #{comment_id}.")
                st.rerun()
        if ingest_cols[1].button("Add Demo Comments"):
            demo_comments = [
                ("Weekend brisket promo", "Maya", "Do you cater birthday parties next weekend?"),
                ("Late night delivery post", "Chris", "Where are you parked after the club tonight?"),
                ("Rib plate photo", "Denise", "Those ribs look amazing!"),
            ]
            with st.spinner("Adding demo comments..."):
                for demo_source, demo_name, demo_text in demo_comments:
                    db.add_facebook_comment(demo_source, demo_name, demo_text)
            toast_success("Demo comments added.")
            st.rerun()

    rows = db.list_facebook_comments(100)
    st.markdown("#### Comment Inbox")
    if not rows:
        st.write("No comments ingested yet.")
        return

    for row in rows:
        (
            comment_id,
            source_post,
            commenter_name,
            comment_text,
            classification,
            suggested_reply,
            status,
            last_reply_attempt_at,
            reply_status,
            error_message,
            created_at,
            _updated_at,
            facebook_post_id,
            facebook_comment_id,
        ) = row
        comment = {
            "id": comment_id,
            "facebook_post_id": facebook_post_id,
            "facebook_comment_id": facebook_comment_id,
            "source_post": source_post,
            "commenter_name": commenter_name,
            "comment_text": comment_text,
            "classification": classification,
            "suggested_reply": suggested_reply,
            "status": status,
        }

        with st.container(border=True):
            header_cols = st.columns([2, 1, 1])
            header_cols[0].markdown(f"**{commenter_name or 'Facebook user'}**")
            header_cols[0].caption(f"{source_post or 'Unknown post'} | Created: {created_at}")
            if facebook_comment_id:
                header_cols[0].caption(f"Facebook comment ID: {facebook_comment_id} | Post ID: {facebook_post_id or 'unknown'}")
            header_cols[1].markdown(f"`{(classification or 'unclassified').upper()}`")
            header_cols[2].markdown(badge(status or "new"), unsafe_allow_html=True)
            st.markdown(
                f'<div class="sbg-preview">{html.escape(comment_text or "No comment text saved.")}</div>',
                unsafe_allow_html=True,
            )

            action_cols = st.columns(4)
            if action_cols[0].button("Classify", key=f"classify_comment_{comment_id}"):
                with st.spinner("Classifying comment..."):
                    comment_class = classify_comment(comment_text)
                    db.update_facebook_comment_classification(comment_id, comment_class)
                toast_success("Comment classified.")
                st.rerun()

            if action_cols[1].button("Generate Reply", key=f"generate_reply_{comment_id}"):
                comment_class = classification or classify_comment(comment_text)
                if not classification:
                    db.update_facebook_comment_classification(comment_id, comment_class)
                with st.spinner("Generating reply draft..."):
                    reply = generate_ai_reply(comment_text, comment_class)
                    db.update_facebook_comment_reply(comment_id, reply, "reply_drafted")
                toast_success("AI reply draft generated.")
                st.rerun()

            if action_cols[2].button("Approve Reply", key=f"approve_reply_{comment_id}"):
                if not suggested_reply:
                    st.warning("Generate or write a reply before approval.")
                else:
                    with st.spinner("Approving reply..."):
                        db.update_facebook_comment_reply(comment_id, suggested_reply, "approved")
                    toast_success("Reply approved.")
                    st.rerun()

            if action_cols[3].button("Simulate Reply", key=f"simulate_reply_{comment_id}"):
                if status != "approved":
                    st.warning("Approve the reply before simulating publishing.")
                else:
                    with st.spinner("Simulating reply publishing..."):
                        result = publish_comment_reply(comment, suggested_reply or "")
                    next_status = "simulated_replied" if result["success"] else "failed"
                    db.update_facebook_comment_reply_attempt(
                        comment_id,
                        next_status,
                        result.get("message", ""),
                        "" if result["success"] else result.get("message", ""),
                    )
                    db.add_facebook_comment_reply_log(
                        comment_id,
                        next_status,
                        suggested_reply or "",
                        result.get("message", ""),
                        "" if result["success"] else result.get("message", ""),
                    )
                    if result["success"]:
                        toast_success(result["message"])
                    else:
                        st.error(result["message"])
                    st.rerun()

            with st.container(border=True):
                st.markdown("**Reply draft workspace**")
                st.caption("Review and edit before approval. Live replies stay disabled.")
                edited_reply = st.text_area(
                    "Reply draft",
                    value=suggested_reply or "",
                    height=120,
                    key=f"comment_reply_text_{comment_id}",
                    placeholder="Generate a reply, then edit it before approval.",
                )
                save_cols = st.columns([1, 3])
                if save_cols[0].button("Save Reply Draft", key=f"save_reply_draft_{comment_id}"):
                    if not edited_reply.strip():
                        st.warning("Reply draft cannot be empty.")
                    else:
                        with st.spinner("Saving reply draft..."):
                            db.update_facebook_comment_reply(comment_id, edited_reply, "reply_drafted")
                        toast_success("Reply draft saved.")
                        st.rerun()

            if last_reply_attempt_at or reply_status:
                st.caption(f"Last reply attempt: {last_reply_attempt_at or 'Not attempted'} | Reply status: {reply_status or 'none'}")
            if error_message:
                st.error(error_message)


def build_menu_intelligence_prompt(
    specialties: str,
    weekly_specials: str,
    happy_hour: str,
    delivery_options: str,
    audience: str,
    goal: str,
    platform: str,
    tone: str,
    n: int,
) -> str:
    return (
        "Create a smart marketing plan for Savannah Smokes based on the menu, specials, and business goal below.\n\n"
        f"Menu specialties:\n{specialties or 'Brisket, ribs, pulled pork, wings, mac and cheese, cornbread, sweet tea'}\n\n"
        f"Weekly specials:\n{weekly_specials or 'No weekly specials provided'}\n\n"
        f"Happy hour offers:\n{happy_hour or 'No happy hour offers provided'}\n\n"
        f"Delivery offers:\n{delivery_options or 'Special delivery, weekly delivery, after-hours delivery, after-club-hours food, and home delivery'}\n\n"
        f"Target customer:\n{audience or 'Local BBQ fans, families, event guests, and catering customers'}\n"
        f"Business goal:\n{goal or 'Increase orders, catering inquiries, and social engagement'}\n"
        f"Platform: {platform}\n"
        f"Tone: {tone}\n"
        f"Number of ideas: {n}\n\n"
        "Return a practical business-intelligence style marketing plan with:\n"
        "1. The most appetite-building menu angles\n"
        "2. Weekly specials likely to convert customers\n"
        "3. Happy hour hooks that feel urgent and tasty\n"
        "4. Special delivery, weekly delivery, after-hours, after-club, and home delivery angles\n"
        "5. Suggested bundles or limited-time offers\n"
        "6. Captions/hooks that make Savannah Smokes feel unique, special, craveable, and very tasty\n"
        "7. Hashtags\n"
        "8. Best next action for the owner"
    )


def build_weekly_calendar_prompt(
    specialties: str,
    weekly_specials: str,
    happy_hour: str,
    delivery_options: str,
    campaign_goal: str,
    target_audience: str,
    platforms: list[str],
    tone: str,
) -> str:
    platform_list = ", ".join(platforms) if platforms else "Facebook, Instagram, TikTok"
    return (
        "Create a 7-day restaurant marketing campaign calendar for Savannah Smokes.\n\n"
        f"Signature items / specialties:\n{specialties or 'Brisket, ribs, pulled pork, wings, mac and cheese, cornbread, sweet tea'}\n\n"
        f"Weekly specials:\n{weekly_specials or 'No weekly specials provided'}\n\n"
        f"Happy hour offers:\n{happy_hour or 'No happy hour offers provided'}\n\n"
        f"Delivery offers:\n{delivery_options or 'Special delivery, weekly delivery, after-hours delivery, after-club food, and home delivery'}\n\n"
        f"Campaign goal: {campaign_goal}\n"
        f"Target audience: {target_audience}\n"
        f"Platforms to use: {platform_list}\n"
        f"Tone: {tone}\n\n"
        "Return exactly 7 days. For each day include:\n"
        "- Day\n"
        "- Platform\n"
        "- Campaign focus\n"
        "- Caption draft\n"
        "- Call-to-action\n"
        "- Hashtags\n"
        "- Suggested posting time\n"
        "- Owner prep note\n\n"
        "Make the plan practical, promotion-focused, and varied across the week. "
        "Use Facebook for community/family/local posts, Instagram for visual food storytelling, "
        "and TikTok for short hook-driven ideas. Emphasize tasty, unique, craveable food and business growth."
    )


def render_weekly_campaign_planner(tone: str, cost_per_1k: float):
    st.subheader("Campaign Calendar / Weekly Planner")
    st.caption("Generate a 7-day posting plan from specials, happy hour, delivery, and platform goals.")

    with st.form("weekly_campaign_planner_form"):
        specialties = st.text_area(
            "Signature items / specialties",
            value="Brisket, ribs, pulled pork, wings, mac and cheese, cornbread, sweet tea",
            height=90,
        )
        weekly_specials = st.text_area(
            "Weekly specials",
            placeholder="Example: Tuesday rib plate, Friday brisket tray, Sunday family combo",
            height=90,
        )
        happy_hour = st.text_area(
            "Happy hour offers",
            placeholder="Example: 4-6 PM wings special, loaded fries deal, sweet tea combo",
            height=90,
        )
        delivery_options = st.text_area(
            "Delivery offers",
            placeholder="Example: weekly delivery routes, late-night plates, after-club-hours food, home delivery",
            height=90,
        )
        cols = st.columns(2)
        campaign_goal = cols[0].selectbox("Campaign Goal", CAMPAIGN_GOALS, key="weekly_campaign_goal")
        target_audience = cols[1].selectbox("Target Audience", TARGET_AUDIENCES, key="weekly_target_audience")
        platforms = st.multiselect(
            "Platforms",
            ["Facebook", "Instagram", "TikTok"],
            default=["Facebook", "Instagram", "TikTok"],
        )
        submitted = st.form_submit_button("Generate 7-day campaign calendar")

    if not submitted:
        return

    with st.spinner("Building the weekly marketing calendar..."):
        try:
            prompt = build_weekly_calendar_prompt(
                specialties=specialties,
                weekly_specials=weekly_specials,
                happy_hour=happy_hour,
                delivery_options=delivery_options,
                campaign_goal=campaign_goal,
                target_audience=target_audience,
                platforms=platforms,
                tone=tone,
            )
            result, usage = generate_content(prompt)
        except Exception as exc:
            st.error("Could not generate weekly campaign calendar.")
            st.write(str(exc))
            return

    st.success("7-day campaign calendar generated.")
    st.session_state["latest_generation"] = {
        "task": "Weekly Campaign Planner",
        "platform": ", ".join(platforms) if platforms else "General",
        "tone": tone,
        "input": campaign_goal,
        "result": result,
        "media_name": None,
    }
    st.session_state["show_prepared_facebook_post"] = False
    st.text_area("Weekly campaign calendar", value=result, height=460)
    st.download_button(
        "Download weekly campaign calendar",
        result,
        file_name="savannah_smokes_weekly_campaign_calendar.txt",
        mime="text/plain",
    )

    if usage:
        total_t = usage.get("total_tokens")
        actual_cost = (total_t or 0) / 1000.0 * float(cost_per_1k)
        st.caption(f"Usage: {total_t} tokens. Estimated cost: ${actual_cost:.4f}")

    try:
        saved_input = (
            f"Specialties: {specialties}\n"
            f"Weekly specials: {weekly_specials or 'None provided'}\n"
            f"Happy hour: {happy_hour or 'None provided'}\n"
            f"Delivery offers: {delivery_options or 'None provided'}\n"
            f"Campaign goal: {campaign_goal}\n"
            f"Target audience: {target_audience}\n"
            f"Platforms: {', '.join(platforms) if platforms else 'None selected'}"
        )
        db.save_result("Weekly Campaign Planner", ", ".join(platforms) if platforms else "General", tone, saved_input, result)
        st.success("Saved weekly campaign calendar to local history.")
    except Exception as exc:
        st.warning(f"Could not save weekly campaign calendar: {exc}")


def render_menu_specials_lab(platform: str, tone: str, cost_per_1k: float):
    st.subheader("Menu & Specials Lab")
    st.caption("Turn menu items, specials, and customer targets into smarter promotions.")

    with st.form("menu_specials_form"):
        specialties = st.text_area(
            "Signature items / specialties",
            value="Brisket, ribs, pulled pork, wings, mac and cheese, cornbread, sweet tea",
            height=100,
        )
        weekly_specials = st.text_area(
            "Weekly specials",
            placeholder="Example: Tuesday rib plate, Friday brisket tray, Sunday family combo",
            height=90,
        )
        happy_hour = st.text_area(
            "Happy hour offers",
            placeholder="Example: 4-6 PM wings special, loaded fries deal, sweet tea combo, after-work BBQ plate",
            height=100,
        )
        delivery_options = st.text_area(
            "Delivery offers",
            placeholder="Example: special delivery, weekly delivery routes, after-club-hours food, late-night plates, home delivery",
            height=100,
        )
        cols = st.columns(2)
        audience = cols[0].text_input(
            "Target customer",
            value="Local families, BBQ fans, event guests, and catering customers",
        )
        goal = cols[1].text_input(
            "Business goal",
            value="Drive weekend orders and catering leads",
        )
        idea_count = st.slider("Number of menu marketing ideas", min_value=1, max_value=10, value=5)
        submitted = st.form_submit_button("Generate menu marketing ideas")

    if not submitted:
        return

    with st.spinner("Finding tasty, promotion-ready angles..."):
        try:
            prompt = build_menu_intelligence_prompt(
                specialties=specialties,
                weekly_specials=weekly_specials,
                happy_hour=happy_hour,
                delivery_options=delivery_options,
                audience=audience,
                goal=goal,
                platform=platform,
                tone=tone,
                n=idea_count,
            )
            result, usage = generate_content(prompt)
        except Exception as exc:
            st.error("Could not generate menu marketing ideas.")
            st.write(str(exc))
            return

    st.success("Menu marketing ideas generated.")
    st.session_state["latest_generation"] = {
        "task": "Menu & Specials Lab",
        "platform": platform,
        "tone": tone,
        "input": goal,
        "result": result,
        "media_name": None,
    }
    st.session_state["show_prepared_facebook_post"] = False
    st.text_area("Menu intelligence output", value=result, height=360)
    st.download_button(
        "Download menu marketing plan",
        result,
        file_name="savannah_smokes_menu_marketing_plan.txt",
        mime="text/plain",
    )

    if usage:
        total_t = usage.get("total_tokens")
        actual_cost = (total_t or 0) / 1000.0 * float(cost_per_1k)
        st.caption(f"Usage: {total_t} tokens. Estimated cost: ${actual_cost:.4f}")

    try:
        saved_input = (
            f"Specialties: {specialties}\n"
            f"Weekly specials: {weekly_specials or 'None provided'}\n"
            f"Happy hour: {happy_hour or 'None provided'}\n"
            f"Delivery offers: {delivery_options or 'None provided'}\n"
            f"Audience: {audience}\n"
            f"Goal: {goal}"
        )
        db.save_result("Menu & Specials Lab", platform, tone, saved_input, result)
        st.success("Saved menu marketing plan to local history.")
    except Exception as exc:
        st.warning(f"Could not save menu marketing plan: {exc}")


def render_social_media_integration_guide():
    st.subheader("Social Media Integration Path")
    st.caption("A business-safe path from generated content to future Facebook/Instagram publishing.")

    facebook_config = validate_facebook_config()
    if facebook_config["ready"]:
        st.success("Facebook placeholder config is present. Real posting is still disabled.")
    else:
        st.info(f"Facebook placeholder only. Missing config: {', '.join(facebook_config['missing'])}")

    st.markdown(
        """
        **Current safe workflow**

        1. Generate caption, hashtags, and promo copy.
        2. Use **Prepare Facebook Post** after generation.
        3. Review/edit the package.
        4. Manually publish on Facebook or Instagram.

        **Next technical step**

        Add a Meta connection screen that stores page/account settings outside the codebase, then use the
        Meta Graph API only after owner approval.

        **What Meta setup needs**

        - Facebook Business Page for Savannah Smokes
        - Admin access to that Page
        - Meta Developer account and Meta app
        - Facebook Login configured
        - Page access token
        - Permissions such as `pages_manage_posts` and `pages_read_engagement`
        - App Review before publishing for users beyond the admin/test account

        **Recommended product sequence**

        Keep the app in review-first mode now. Add direct publishing later as a separate owner-approved step:
        `Generate -> Review/Edit -> Prepare Post -> Publish to Facebook Page`.
        """
    )


def render_prepared_facebook_post():
    generation = st.session_state.get("latest_generation")
    if not generation:
        return

    st.markdown("---")
    st.subheader("Facebook post preparation")
    st.caption("Prepare a review-ready package without posting to Meta yet.")

    if st.button("Prepare Facebook Post"):
        st.session_state["show_prepared_facebook_post"] = True

    if not st.session_state.get("show_prepared_facebook_post"):
        return

    package = build_facebook_post_package(generation)
    st.success("Facebook post package is ready for owner review.")
    st.text_area("Prepared Facebook post package", value=package, height=300)
    st.download_button(
        "Download Facebook post package",
        package,
        file_name="savannah_smokes_facebook_post.txt",
        mime="text/plain",
    )


def render_saved_outputs():
    rows = db.list_results(500)
    st.subheader("Saved generation history")
    if not rows:
        st.info("No saved outputs yet")
        return

    for key, default in {
        "history_task_filter": "All",
        "history_platform_filter": "All",
        "history_tone_filter": "All",
        "history_search": "",
        "history_page": 1,
        "history_page_size": 10,
    }.items():
        st.session_state.setdefault(key, default)

    def reset_history_page():
        st.session_state["history_page"] = 1

    def reset_history_filters():
        st.session_state["history_task_filter"] = "All"
        st.session_state["history_platform_filter"] = "All"
        st.session_state["history_tone_filter"] = "All"
        st.session_state["history_search"] = ""
        reset_history_page()

    all_tasks = ["All"] + sorted({row[1] for row in rows if row[1]})
    all_platforms = ["All"] + sorted({row[2] for row in rows if row[2]})
    all_tones = ["All"] + sorted({row[3] for row in rows if row[3]})

    if st.session_state["history_task_filter"] not in all_tasks:
        st.session_state["history_task_filter"] = "All"
    if st.session_state["history_platform_filter"] not in all_platforms:
        st.session_state["history_platform_filter"] = "All"
    if st.session_state["history_tone_filter"] not in all_tones:
        st.session_state["history_tone_filter"] = "All"

    task_counts = Counter(row[1] or "Unknown" for row in rows)
    platform_counts = Counter(row[2] or "Unknown" for row in rows)
    tone_counts = Counter(row[3] or "Unknown" for row in rows)

    metric_cols = st.columns(4)
    metric_cols[0].metric("Saved entries", len(rows))
    metric_cols[1].metric("Tasks", len(task_counts))
    metric_cols[2].metric("Platforms", len(platform_counts))
    metric_cols[3].metric("Tones", len(tone_counts))

    with st.expander("Analytics snapshot", expanded=False):
        analytics_cols = st.columns(3)
        analytics_cols[0].markdown("**Top tasks**")
        analytics_cols[0].write(dict(task_counts.most_common(5)))
        analytics_cols[1].markdown("**Top platforms**")
        analytics_cols[1].write(dict(platform_counts.most_common(5)))
        analytics_cols[2].markdown("**Top tones**")
        analytics_cols[2].write(dict(tone_counts.most_common(5)))

    st.markdown("#### Find saved results")
    filter_cols = st.columns([1.2, 1.2, 1.2, 1.8])
    task_filter = filter_cols[0].selectbox(
        "Task",
        options=all_tasks,
        key="history_task_filter",
        on_change=reset_history_page,
    )
    platform_filter = filter_cols[1].selectbox(
        "Platform",
        options=all_platforms,
        key="history_platform_filter",
        on_change=reset_history_page,
    )
    tone_filter = filter_cols[2].selectbox(
        "Tone",
        options=all_tones,
        key="history_tone_filter",
        on_change=reset_history_page,
    )
    search_text = filter_cols[3].text_input(
        "Search prompt or output",
        placeholder="Try: brisket, catering, event, hashtag...",
        key="history_search",
        on_change=reset_history_page,
    )

    st.button("Reset history filters", on_click=reset_history_filters)

    filtered = []
    for row in rows:
        rid, rtask, rplatform, rtone, rinput, routput, created_at = row
        haystack = f"{rtask or ''} {rplatform or ''} {rtone or ''} {rinput or ''} {routput or ''}".lower()
        if task_filter != "All" and rtask != task_filter:
            continue
        if platform_filter != "All" and rplatform != platform_filter:
            continue
        if tone_filter != "All" and rtone != tone_filter:
            continue
        if search_text and search_text.lower() not in haystack:
            continue
        filtered.append(row)

    st.markdown(f"**Showing {len(filtered)} of {len(rows)} saved entries**")

    if not filtered:
        st.warning("No saved results match your filters.")
        return

    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(["id", "task", "platform", "tone", "input", "output", "created_at"])
    for row in filtered:
        writer.writerow(row)

    st.download_button(
        "Export filtered saved results",
        csv_buffer.getvalue(),
        file_name="savannah_bbq_saved_outputs.csv",
        mime="text/csv",
    )

    page_cols = st.columns([1, 1, 2])
    page_size = page_cols[0].selectbox(
        "Results per page",
        options=[5, 10, 20, 50],
        key="history_page_size",
        on_change=reset_history_page,
    )
    total_pages = max(1, (len(filtered) + page_size - 1) // page_size)
    if st.session_state["history_page"] > total_pages:
        st.session_state["history_page"] = total_pages
    page = page_cols[1].number_input(
        "Page",
        min_value=1,
        max_value=total_pages,
        step=1,
        key="history_page",
    )
    page_cols[2].markdown(f"Page **{page}** of **{total_pages}**")

    start = (page - 1) * page_size
    end = start + page_size
    visible_rows = filtered[start:end]

    st.markdown("#### Recent results")
    for rid, rtask, rplatform, rtone, rinput, routput, created_at in visible_rows:
        with st.container(border=True):
            header_cols = st.columns([4, 1])
            header_cols[0].markdown(f"**{rtask or 'Untitled task'}**")
            header_cols[0].caption(f"{created_at} | {rplatform or 'No platform'} | {rtone or 'No tone'} | ID {rid}")

            if header_cols[1].button("Delete", key=f"delete_{rid}"):
                st.session_state["pending_delete_id"] = rid

            if st.session_state.get("pending_delete_id") == rid:
                st.warning("Delete this saved output? This cannot be undone.")
                confirm_cols = st.columns(2)
                if confirm_cols[0].button("Confirm delete", key=f"confirm_delete_{rid}"):
                    db.delete_result(rid)
                    st.session_state.pop("pending_delete_id", None)
                    st.success("Deleted saved output.")
                    st.rerun()
                if confirm_cols[1].button("Cancel", key=f"cancel_delete_{rid}"):
                    st.session_state.pop("pending_delete_id", None)
                    st.rerun()

            st.markdown("**Original prompt**")
            st.write(rinput or "_No prompt saved._")

            output_preview = (routput or "").strip()
            if len(output_preview) > 500:
                output_preview = f"{output_preview[:500]}..."
            st.markdown("**Generated output preview**")
            st.write(output_preview or "_No output saved._")

            with st.expander("View full generated output"):
                st.write(routput or "_No output saved._")


def main():
    init_app()

    st.set_page_config(page_title="Savannah BBQ Growth Engine v2", page_icon="🍖")
    apply_demo_styles()
    banner_path = os.path.join("assets", "banner.png")
    logo_path = os.path.join("assets", "logo.png")

    if os.path.exists(banner_path):
        st.image(banner_path, width="stretch")

    cols = st.columns([0.8, 4], vertical_alignment="center")
    if os.path.exists(logo_path):
        cols[0].image(logo_path, width=120)

    cols[1].markdown(
        """
        <div class="sbg-hero">
            <div class="sbg-eyebrow">AI Restaurant Marketing Operating System</div>
            <h1>Savannah BBQ Growth Engine</h1>
            <p>
                Generate campaigns, queue posts, schedule promotions, simulate publishing, handle comment replies,
                and track growth signals from one polished local MVP.
            </p>
            <span class="sbg-chip">Local-first</span>
            <span class="sbg-chip">Social-ready</span>
            <span class="sbg-chip">Brand-safe</span>
            <span class="sbg-chip">Demo Mode ready</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_onboarding_helper()

    st.sidebar.header("Generation controls")
    task = st.sidebar.selectbox(
        "Select task",
        [
            "Campaign Generator",
            "Facebook Reel captions",
            "Short viral hooks",
            "Hashtag Generator",
            "Customer comment replies",
            "Weekend promo post ideas",
            "Event announcements",
            "Catering promotions",
            "Email campaigns",
            "Image upload caption generator",
            "Video upload caption generator",
        ],
    )

    platform_options = (
        ["Facebook", "Instagram", "TikTok"]
        if task == "Campaign Generator"
        else ["Facebook", "Instagram", "TikTok", "Threads", "LinkedIn", "General"]
    )
    platform = st.sidebar.selectbox("Platform", platform_options)
    tone = st.sidebar.selectbox(
        "Tone",
        ["Friendly", "Playful", "Bold", "Professional", "Authentic Southern", "Urgent"],
    )
    num = st.sidebar.slider("Number of results", min_value=1, max_value=10, value=3)
    cost_per_1k = st.sidebar.number_input(
        "Estimated cost per 1K tokens ($)",
        min_value=0.0001,
        max_value=0.1000,
        value=0.0020,
        step=0.0001,
        format="%.6f",
    )
    save_to_db = st.sidebar.checkbox("Save results locally", value=True)
    show_saved = st.sidebar.checkbox("Show saved outputs", value=False)

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**OpenAI SDK:** {openai.__version__}")

    if not OPENAI_API_KEY:
        st.error("OPENAI_API_KEY not found. Add your key to .env and restart the app.")
        st.stop()

    intelligence_tab, planner_tab, queue_tab, analytics_tab, comments_tab, social_tab = st.tabs(
        ["Menu & Specials Lab", "Weekly Planner", "Content Queue", "Analytics", "Comment Automation", "Social Media Setup"]
    )
    with intelligence_tab:
        render_menu_specials_lab(platform, tone, cost_per_1k)
    with planner_tab:
        render_weekly_campaign_planner(tone, cost_per_1k)
    with queue_tab:
        try:
            render_content_queue()
        except Exception as exc:
            st.warning("Content Queue could not load. Other app features are still available.")
            st.caption(str(exc))
    with analytics_tab:
        try:
            render_analytics_dashboard()
        except Exception as exc:
            st.warning("Analytics Dashboard could not load. Other app features are still available.")
            st.caption(str(exc))
    with comments_tab:
        try:
            render_facebook_comment_automation_center()
        except Exception as exc:
            st.warning("Facebook Comment Automation Center could not load. Other app features are still available.")
            st.caption(str(exc))
    with social_tab:
        render_social_media_integration_guide()

    st.markdown("---")
    st.subheader("AI content generator")

    # Example prompt buttons/selectors to speed up input for the owner
    examples = {
        "Facebook Reel captions": [
            "Weekend smoked brisket special with ribs, mac and cheese, cornbread, and sweet tea",
            "Join us tonight for live music and half-price wings — see you at the truck!",
        ],
        "Hashtag Generator": [
            "Weekend smoked brisket special with ribs, mac and cheese, cornbread, and sweet tea",
            "Catering for graduation parties with bulk trays and discounts",
        ],
        "Email campaigns": [
            "Announcing our catering special for graduations: discount and bulk trays",
            "Monthly newsletter: new menu items and community events",
        ],
        "Customer comment replies": [
            "Customer: Loved the brisket! When's the next pop-up?",
            "Customer: Do you have vegetarian options?",
        ],
        "Campaign Generator": [
            "Brisket plate weekend special for local families",
            "Late-night pulled pork delivery promo for the nightlife crowd",
        ],
        "Image upload caption generator": [
            "Turn this BBQ photo into a weekend promo with a friendly call-to-action",
            "Write captions that highlight smoky flavor, local pride, and catering availability",
        ],
        "Video upload caption generator": [
            "Turn this short BBQ clip into TikTok hooks and social captions",
            "Promote this food truck video for late-night orders and delivery",
        ],
        "default": [
            "Weekend smoked brisket special with ribs, mac and cheese, cornbread, and sweet tea",
        ],
    }

    if task == "Campaign Generator":
        label = ""
        height = 0
    elif task == "Customer comment replies":
        label = "Customer comment:"
        height = 140
    elif task == "Image upload caption generator":
        label = "Optional notes for this image:"
        height = 120
    elif task == "Video upload caption generator":
        label = "Optional notes for this video:"
        height = 120
    else:
        label = "Describe the reel, post, or promo context:"
        height = 180

    # prepare session_state key for input
    if "user_input" not in st.session_state:
        st.session_state["user_input"] = ""

    if task == "Campaign Generator":
        st.markdown("#### Campaign setup")
        st.caption("Build a platform-aware campaign from business context, not just a generic caption.")

        menu_item = st.text_input(
            "Menu item or special",
            value=st.session_state.get("campaign_menu_item", "Weekend brisket plate"),
            key="campaign_menu_item",
        )
        campaign_cols = st.columns(3)
        campaign_goal = campaign_cols[0].selectbox("Campaign Goal", CAMPAIGN_GOALS, key="campaign_goal")
        target_audience = campaign_cols[1].selectbox("Target Audience", TARGET_AUDIENCES, key="target_audience")
        promotion_type = campaign_cols[2].selectbox("Promotion Type", PROMOTION_TYPES, key="promotion_type")
        campaign_notes = st.text_area(
            "Extra business context",
            placeholder="Example: limited quantities, delivery available, family trays, after-hours orders, catering availability",
            height=100,
            key="campaign_notes",
        )
        user_input = "\n".join(
            [
                f"Menu item or special: {menu_item}",
                f"Campaign goal: {campaign_goal}",
                f"Target audience: {target_audience}",
                f"Promotion type: {promotion_type}",
                f"Extra business context: {campaign_notes or 'No extra context provided.'}",
            ]
        )
    else:
        opts = examples.get(task, examples["default"])[:3]
        choice = st.selectbox("Insert example prompt", ["— choose example —"] + opts, key="example_choice")
        if choice and choice != "— choose example —":
            st.session_state["user_input"] = choice

        user_input = st.text_area(label, value=st.session_state.get("user_input", ""), height=height, key="user_input")

    uploaded_image = None
    uploaded_video = None
    if task == "Image upload caption generator":
        st.markdown("#### Upload a photo")
        st.caption("Use a BBQ plate, food truck setup, event scene, or branded promo image.")
        uploaded_image = st.file_uploader(
            "Upload BBQ food or event photo",
            type=["png", "jpg", "jpeg", "webp"],
            help="Upload the photo you want captions, hashtags, and promo copy for.",
        )
        if uploaded_image:
            st.image(uploaded_image, caption=f"Uploaded image: {uploaded_image.name}", width="stretch")
    elif task == "Video upload caption generator":
        st.markdown("#### Upload a short video")
        st.caption(f"Recommended: 5-15 seconds. Hard limit: {MAX_VIDEO_SECONDS} seconds or {MAX_VIDEO_UPLOAD_MB} MB.")
        uploaded_video = st.file_uploader(
            "Upload short BBQ video",
            type=["mp4", "mov", "m4v"],
            help="Upload a short food, smoker, food truck, happy hour, or event clip.",
        )
        if uploaded_video:
            video_size_mb = len(uploaded_video.getvalue()) / (1024 * 1024)
            st.video(uploaded_video)
            st.caption(f"Uploaded video: {uploaded_video.name} ({video_size_mb:.1f} MB)")

    if task == "Campaign Generator":
        st.info(PLATFORM_CAMPAIGN_GUIDANCE.get(platform, "Campaign mode will adapt the output to the selected platform."))
    else:
        # Example prompt toolbar for fast demo inputs
        st.markdown("**Quick demo prompts:**")
        demo_cols = st.columns(4)
        if demo_cols[0].button("Weekend brisket special"):
            st.session_state["user_input"] = "Weekend smoked brisket special with ribs, mac and cheese, cornbread, and sweet tea"
        if demo_cols[1].button("Family combo promo"):
            st.session_state["user_input"] = "Family combo promo with pulled pork, loaded fries, and refreshing sweet tea for the whole crew"
        if demo_cols[2].button("Catering order promo"):
            st.session_state["user_input"] = "Catering order promo for graduation parties, office lunches, and large family gatherings"
        if demo_cols[3].button("Friday event announcement"):
            st.session_state["user_input"] = "Friday event announcement with live music, drink specials, and late-night BBQ feast"

    if task == "Campaign Generator" and not menu_item.strip():
        st.warning("Add a menu item or special before generating a campaign.")
    elif task == "Image upload caption generator" and not uploaded_image:
        st.warning("Upload an image before generating photo-based captions.")
    elif task == "Video upload caption generator" and not uploaded_video:
        st.warning("Upload a short video before generating video-based captions.")
    elif not user_input.strip():
        st.warning("Enter some context before generating. The clearer the description, the better the results.")

    if st.button("Generate content"):
        if task == "Campaign Generator" and not menu_item.strip():
            st.error("Please add a menu item or special before generating a campaign.")
        elif task == "Image upload caption generator" and not uploaded_image:
            st.error("Please upload an image before generating photo-based captions.")
        elif task == "Video upload caption generator" and not uploaded_video:
            st.error("Please upload a short video before generating video-based captions.")
        elif task not in ("Image upload caption generator", "Video upload caption generator") and not user_input.strip():
            st.error("Please add some context or a customer comment before generating.")
        else:
            with st.spinner("Generating your copy..."):
                try:
                    prompt = build_task_prompt(task, user_input, tone, platform, num)
                    # show estimated cost before calling the API
                    est_prompt_tokens = max(1, len(prompt) // 4)
                    est_completion_tokens = 500
                    est_total = est_prompt_tokens + est_completion_tokens
                    est_cost = est_total / 1000.0 * float(cost_per_1k)
                    st.info(
                        f"Estimated tokens: {est_total}\nEstimated request cost: ${est_cost:.4f}"
                    )

                    optimized_image_message = None
                    video_processing_message = None
                    if task == "Image upload caption generator":
                        original_image_bytes = uploaded_image.getvalue()
                        image_bytes, image_mime = optimize_image_for_vision(original_image_bytes)
                        original_size_kb = len(original_image_bytes) / 1024
                        optimized_size_kb = len(image_bytes) / 1024
                        reduction_pct = max(0, 100 - (optimized_size_kb / original_size_kb * 100))
                        optimized_image_message = (
                            f"Optimized image for AI: {original_size_kb:.0f} KB -> {optimized_size_kb:.0f} KB "
                            f"({reduction_pct:.0f}% smaller)."
                        )
                        result, usage = generate_image_content(prompt, image_bytes, image_mime)
                    elif task == "Video upload caption generator":
                        video_bytes = uploaded_video.getvalue()
                        video_size_mb = len(video_bytes) / (1024 * 1024)
                        if video_size_mb > MAX_VIDEO_UPLOAD_MB:
                            raise RuntimeError(
                                f"Video is {video_size_mb:.1f} MB. Please upload a video {MAX_VIDEO_UPLOAD_MB} MB or smaller."
                            )

                        suffix = os.path.splitext(uploaded_video.name)[1] or ".mp4"
                        frames, duration = extract_video_frames_for_vision(video_bytes, suffix)
                        video_processing_message = (
                            f"Sampled {len(frames)} frame(s) from a {duration:.1f}s video for AI analysis."
                        )
                        result, usage = generate_video_content(prompt, frames)
                    else:
                        result, usage = generate_content(prompt)
                except Exception as exc:
                    st.error("Failed to generate content.")
                    st.write(str(exc))
                    return

                st.session_state["latest_generation"] = {
                    "task": task,
                    "platform": platform,
                    "tone": tone,
                    "input": user_input,
                    "result": result,
                    "media_name": (
                        uploaded_image.name
                        if task == "Image upload caption generator" and uploaded_image
                        else uploaded_video.name
                        if task == "Video upload caption generator" and uploaded_video
                        else None
                    ),
                }
                st.session_state["show_prepared_facebook_post"] = False

                st.success("Generated fresh marketing copy.")

                if task == "Image upload caption generator":
                    st.subheader("Generated from uploaded image")
                    if optimized_image_message:
                        st.caption(optimized_image_message)

                    output_cols = st.columns([1, 1.2])
                    with output_cols[0]:
                        st.markdown("**Source image**")
                        st.image(uploaded_image, caption=uploaded_image.name, width="stretch")
                        st.info("Generated from uploaded image")
                    with output_cols[1]:
                        st.markdown("**Copy-friendly output**")
                        st.text_area("Image-generated copy", value=result, height=360)
                elif task == "Video upload caption generator":
                    st.subheader("Generated from uploaded video")
                    if video_processing_message:
                        st.caption(video_processing_message)

                    output_cols = st.columns([1, 1.2])
                    with output_cols[0]:
                        st.markdown("**Source video**")
                        st.video(uploaded_video)
                        st.info("Generated from sampled video frames")
                    with output_cols[1]:
                        st.markdown("**Copy-friendly output**")
                        st.text_area("Video-generated copy", value=result, height=360)
                else:
                    if task == "Campaign Generator":
                        st.subheader(f"{platform} campaign output")
                        st.text_area("Platform-aware campaign", value=result, height=320)
                    else:
                        st.subheader("Generated output")
                        st.text_area("Copy-friendly output", value=result, height=260)

                st.download_button("Download result as text", result, file_name="savannah_bbq_result.txt", mime="text/plain")

                # show actual usage/cost when available
                if usage:
                    prompt_t = usage.get("prompt_tokens")
                    completion_t = usage.get("completion_tokens")
                    total_t = usage.get("total_tokens")
                    actual_cost = (total_t or 0) / 1000.0 * float(cost_per_1k)
                    st.success(
                        f"OpenAI usage — prompt: {prompt_t}, completion: {completion_t}, total: {total_t}. Actual request cost: ${actual_cost:.4f}"
                    )

                escaped_result = html.escape(result)
                copy_html = """
                    <div>
                      <button id="clipboard-btn" style="background-color:#4B8BBE;color:white;border:none;padding:10px 14px;border-radius:6px;cursor:pointer;font-size:14px;">
                        Copy to clipboard
                      </button>
                      <span id="clipboard-status" style="margin-left:12px;color:#4B8BBE;font-weight:600;font-size:14px;"></span>
                      <div id="copy-data" style="display:none;">{copy_text}</div>
                    </div>
                    <script>
                      const button = document.getElementById("clipboard-btn");
                      const status = document.getElementById("clipboard-status");
                      const text = document.getElementById("copy-data").innerText;
                      button.onclick = async () => {{
                        try {{
                          await navigator.clipboard.writeText(text);
                          status.textContent = "Copied!";
                          setTimeout(() => status.textContent = "", 1500);
                        }} catch (err) {{
                          status.textContent = "Copy failed";
                        }}
                      }};
                    </script>
                """.format(copy_text=escaped_result)
                components.html(copy_html, height=100)

                st.markdown("**Tip:** click the button to copy the generated text automatically.")

                if save_to_db:
                    try:
                        saved_input = user_input
                        if task == "Image upload caption generator" and uploaded_image:
                            saved_input = f"Image: {uploaded_image.name}\nNotes: {user_input or 'No extra notes provided.'}"
                        elif task == "Video upload caption generator" and uploaded_video:
                            saved_input = f"Video: {uploaded_video.name}\nNotes: {user_input or 'No extra notes provided.'}"
                        db.save_result(task, platform, tone, saved_input, result)
                        st.success("Saved result to local database.")
                    except Exception as exc:
                        st.warning(f"Could not save result: {exc}")

    render_prepared_facebook_post()

    if show_saved:
        render_saved_outputs()


if __name__ == "__main__":
    main()

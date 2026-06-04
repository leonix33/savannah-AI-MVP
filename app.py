import os
import io
import csv
import html
import base64
from collections import Counter
from dotenv import load_dotenv
import streamlit as st
import streamlit.components.v1 as components
import openai
from PIL import Image, ImageOps
from utils import db

load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")
TEXT_MODEL = os.environ.get("OPENAI_TEXT_MODEL", "gpt-3.5-turbo")
VISION_MODEL = os.environ.get("OPENAI_VISION_MODEL", "gpt-4o-mini")
MAX_IMAGE_SIDE = int(os.environ.get("MAX_IMAGE_SIDE", "1024"))
IMAGE_JPEG_QUALITY = int(os.environ.get("IMAGE_JPEG_QUALITY", "82"))


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


def build_task_prompt(task: str, user_input: str, tone: str, platform: str, n: int) -> str:
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


def build_menu_intelligence_prompt(
    specialties: str,
    weekly_specials: str,
    happy_hour: str,
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
        f"Target customer:\n{audience or 'Local BBQ fans, families, event guests, and catering customers'}\n"
        f"Business goal:\n{goal or 'Increase orders, catering inquiries, and social engagement'}\n"
        f"Platform: {platform}\n"
        f"Tone: {tone}\n"
        f"Number of ideas: {n}\n\n"
        "Return a practical business-intelligence style marketing plan with:\n"
        "1. The most appetite-building menu angles\n"
        "2. Weekly specials likely to convert customers\n"
        "3. Happy hour hooks that feel urgent and tasty\n"
        "4. Suggested bundles or limited-time offers\n"
        "5. Caption/hooks for social media\n"
        "6. Hashtags\n"
        "7. Best next action for the owner"
    )


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
    banner_path = os.path.join("assets", "banner.png")
    logo_path = os.path.join("assets", "logo.png")

    if os.path.exists(banner_path):
        st.image(banner_path, use_column_width=True)

    cols = st.columns([1, 3])
    if os.path.exists(logo_path):
        cols[0].image(logo_path, width=120)

    cols[1].markdown("""
    ## Savannah BBQ Growth Engine — v2
    AI-powered marketing copy for your food truck.
    Create local captions, viral hashtags, promotional posts, photo-based captions, replies, event announcements, catering promos, and email campaigns.
    """)

    st.markdown("---")
    st.markdown(
        "**Local-first. Social-ready. Brand-safe.** Built for Savannah BBQ to help you publish faster and stay consistent across channels."
    )

    st.sidebar.header("Generation controls")
    task = st.sidebar.selectbox(
        "Select task",
        [
            "Facebook Reel captions",
            "Short viral hooks",
            "Hashtag Generator",
            "Customer comment replies",
            "Weekend promo post ideas",
            "Event announcements",
            "Catering promotions",
            "Email campaigns",
            "Image upload caption generator",
        ],
    )

    platform = st.sidebar.selectbox(
        "Platform",
        ["Facebook", "Instagram", "TikTok", "Threads", "LinkedIn", "General"],
    )
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

    intelligence_tab, social_tab = st.tabs(["Menu & Specials Lab", "Social Media Setup"])
    with intelligence_tab:
        render_menu_specials_lab(platform, tone, cost_per_1k)
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
        "Image upload caption generator": [
            "Turn this BBQ photo into a weekend promo with a friendly call-to-action",
            "Write captions that highlight smoky flavor, local pride, and catering availability",
        ],
        "default": [
            "Weekend smoked brisket special with ribs, mac and cheese, cornbread, and sweet tea",
        ],
    }

    if task == "Customer comment replies":
        label = "Customer comment:"
        height = 140
    elif task == "Image upload caption generator":
        label = "Optional notes for this image:"
        height = 120
    else:
        label = "Describe the reel, post, or promo context:"
        height = 180

    # prepare session_state key for input
    if "user_input" not in st.session_state:
        st.session_state["user_input"] = ""

    opts = examples.get(task, examples["default"])[:3]
    choice = st.selectbox("Insert example prompt", ["— choose example —"] + opts, key="example_choice")
    if choice and choice != "— choose example —":
        st.session_state["user_input"] = choice

    user_input = st.text_area(label, value=st.session_state.get("user_input", ""), height=height, key="user_input")

    uploaded_image = None
    if task == "Image upload caption generator":
        st.markdown("#### Upload a photo")
        st.caption("Use a BBQ plate, food truck setup, event scene, or branded promo image.")
        uploaded_image = st.file_uploader(
            "Upload BBQ food or event photo",
            type=["png", "jpg", "jpeg", "webp"],
            help="Upload the photo you want captions, hashtags, and promo copy for.",
        )
        if uploaded_image:
            st.image(uploaded_image, caption=f"Uploaded image: {uploaded_image.name}", use_column_width=True)

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

    if task == "Image upload caption generator" and not uploaded_image:
        st.warning("Upload an image before generating photo-based captions.")
    elif not user_input.strip():
        st.warning("Enter some context before generating. The clearer the description, the better the results.")

    if st.button("Generate content"):
        if task == "Image upload caption generator" and not uploaded_image:
            st.error("Please upload an image before generating photo-based captions.")
        elif task != "Image upload caption generator" and not user_input.strip():
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
                    "media_name": uploaded_image.name if task == "Image upload caption generator" and uploaded_image else None,
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
                        st.image(uploaded_image, caption=uploaded_image.name, use_column_width=True)
                        st.info("Generated from uploaded image")
                    with output_cols[1]:
                        st.markdown("**Copy-friendly output**")
                        st.text_area("Image-generated copy", value=result, height=360)
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
                        db.save_result(task, platform, tone, saved_input, result)
                        st.success("Saved result to local database.")
                    except Exception as exc:
                        st.warning(f"Could not save result: {exc}")

    render_prepared_facebook_post()

    if show_saved:
        render_saved_outputs()


if __name__ == "__main__":
    main()

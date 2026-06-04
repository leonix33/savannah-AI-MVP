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
from utils import db

load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")
TEXT_MODEL = os.environ.get("OPENAI_TEXT_MODEL", "gpt-3.5-turbo")
VISION_MODEL = os.environ.get("OPENAI_VISION_MODEL", "gpt-4o-mini")


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
        uploaded_image = st.file_uploader(
            "Upload BBQ food or event photo",
            type=["png", "jpg", "jpeg", "webp"],
            help="Upload the photo you want captions, hashtags, and promo copy for.",
        )
        if uploaded_image:
            st.image(uploaded_image, caption=uploaded_image.name, use_column_width=True)

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

                    if task == "Image upload caption generator":
                        image_bytes = uploaded_image.getvalue()
                        image_mime = uploaded_image.type or "image/jpeg"
                        result, usage = generate_image_content(prompt, image_bytes, image_mime)
                    else:
                        result, usage = generate_content(prompt)
                except Exception as exc:
                    st.error("Failed to generate content.")
                    st.write(str(exc))
                    return

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

    if show_saved:
        render_saved_outputs()


if __name__ == "__main__":
    main()

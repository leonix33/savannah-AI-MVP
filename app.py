import os
import io
import csv
import html
from dotenv import load_dotenv
import streamlit as st
import streamlit.components.v1 as components
import openai
from utils import db

load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")


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


def generate_content(prompt: str) -> str:
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful, creative social media assistant for a local food truck."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
            max_tokens=500,
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        raise RuntimeError(f"OpenAI generation failed: {exc}") from exc


def build_task_prompt(task: str, user_input: str, tone: str, platform: str, n: int) -> str:
    if task == "Hashtag generator":
        return make_prompt(
            task=task,
            template="Generate {n} hashtag suggestions for {platform} posts about: {input}. Tone: {tone}. Return only hashtags separated by spaces or commas.",
            user_input=user_input,
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
    rows = db.list_results(200)
    st.subheader("Saved outputs")
    if not rows:
        st.info("No saved outputs yet")
        return

    all_tasks = ["All"] + sorted({row[1] for row in rows})
    task_filter = st.selectbox("Filter by saved task", options=all_tasks)
    search_text = st.text_input("Search saved results")

    filtered = []
    for row in rows:
        rid, rtask, rinput, routput, created_at = row
        haystack = f"{rtask} {rinput or ''} {routput or ''}".lower()
        if task_filter != "All" and rtask != task_filter:
            continue
        if search_text and search_text.lower() not in haystack:
            continue
        filtered.append(row)

    if not filtered:
        st.warning("No saved results match your filters.")
        return

    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(["id", "task", "input", "output", "created_at"])
    for row in filtered:
        writer.writerow(row)

    st.download_button(
        "Export filtered saved results",
        csv_buffer.getvalue(),
        file_name="savannah_bbq_saved_outputs.csv",
        mime="text/csv",
    )

    for rid, rtask, rinput, routput, created_at in filtered:
        with st.expander(f"{created_at} — {rtask}"):
            st.markdown(f"**Input:** {rinput}")
            st.markdown("**Output:**")
            st.write(routput)


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
    Create local captions, viral hashtags, promotional posts, replies, event announcements, catering promos, and email campaigns.
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
            "Hashtag generator",
            "Customer comment replies",
            "Weekend promo post ideas",
            "Event announcements",
            "Catering promotions",
            "Email campaigns",
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
    save_to_db = st.sidebar.checkbox("Save results locally", value=True)
    show_saved = st.sidebar.checkbox("Show saved outputs", value=False)

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**OpenAI SDK:** {openai.__version__}")

    if not OPENAI_API_KEY:
        st.error("OPENAI_API_KEY not found. Add your key to .env and restart the app.")
        st.stop()

    if task == "Customer comment replies":
        user_input = st.text_area("Customer comment:", height=140)
    else:
        user_input = st.text_area("Describe the reel, post, or promo context:", height=180)

    if not user_input.strip():
        st.warning("Enter some context before generating. The clearer the description, the better the results.")

    if st.button("Generate content"):
        if not user_input.strip():
            st.error("Please add some context or a customer comment before generating.")
        else:
            with st.spinner("Generating your copy..."):
                try:
                    prompt = build_task_prompt(task, user_input, tone, platform, num)
                    result = generate_content(prompt)
                except Exception as exc:
                    st.error("Failed to generate content.")
                    st.write(str(exc))
                    return

                st.subheader("Generated output")
                st.text_area("Copy-friendly output", value=result, height=260)
                st.download_button("Download result as text", result, file_name="savannah_bbq_result.txt", mime="text/plain")

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

                st.markdown("**Tip:** highlight the generated text, then copy it into your social post.")

                if save_to_db:
                    try:
                        db.save_result(f"{task} | {platform} | {tone}", user_input, result)
                        st.success("Saved result to local database.")
                    except Exception as exc:
                        st.warning(f"Could not save result: {exc}")

    if show_saved:
        render_saved_outputs()


if __name__ == "__main__":
    main()

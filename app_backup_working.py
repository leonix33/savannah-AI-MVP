import os
from dotenv import load_dotenv
import streamlit as st
import openai
import db
import io
import csv

load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")


# initialize local DB (optional)
try:
    db.init_db()
except Exception:
    pass


def load_prompt(filename: str) -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def generate_from_prompt(prompt_template: str, user_input: str, n: int = 3) -> str:
    prompt = prompt_template.format(input=user_input or "", n=n)
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful, creative social media assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
            max_tokens=400,
        )
        return resp["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Error generating content: {e}"


def main():
    st.set_page_config(page_title="Savannah BBQ Growth Engine (MVP)")
    st.title("Savannah BBQ Growth Engine — MVP")

    st.sidebar.header("Settings")
    task = st.sidebar.selectbox(
        "Choose task",
        [
            "Facebook Reel captions",
            "Short viral hooks",
            "Hashtags",
            "Customer comment replies",
            "Weekend promo post ideas",
        ],
    )

    num = st.sidebar.slider("Number of outputs", 1, 10, 3)

    save_to_db = st.sidebar.checkbox("Save outputs to local DB", value=False)
    show_saved = st.sidebar.checkbox("Show saved outputs", value=False)

    if not OPENAI_API_KEY:
        st.error("OPENAI_API_KEY not found. Create a .env with OPENAI_API_KEY and restart.")
        st.stop()

    st.write("Use the fields below to describe the reel, comment, or context.")

    if task == "Customer comment replies":
        user_input = st.text_area("Customer comment", height=120)
    else:
        user_input = st.text_area("Describe the reel / post / promo context", height=160)

    if st.button("Generate"):
        with st.spinner("Generating..."):
            if task == "Facebook Reel captions":
                template = load_prompt("caption_prompt.txt")
                result = generate_from_prompt(template, user_input, n=num)
            elif task == "Short viral hooks":
                template = load_prompt("caption_prompt.txt")
                result = generate_from_prompt(template, user_input, n=num)
            elif task == "Hashtags":
                # short prompt for hashtags
                template = "Generate {n} hashtag suggestions for: {input} — return only hashtags separated by spaces or commas."
                result = generate_from_prompt(template, user_input, n=num)
            elif task == "Customer comment replies":
                template = load_prompt("reply_prompt.txt")
                result = generate_from_prompt(template, user_input, n=num)
            elif task == "Weekend promo post ideas":
                template = load_prompt("promo_prompt.txt")
                result = generate_from_prompt(template, user_input, n=num)
            else:
                result = "Unknown task"

        st.subheader("Results")
        st.text_area("Output", value=result, height=360)

        if save_to_db:
            try:
                db.save_result(task, user_input, result)
                st.success("Saved result to local DB")
            except Exception as e:
                st.warning(f"Could not save result: {e}")

    if show_saved:
        rows = db.list_results(200)
        st.subheader("Saved outputs (most recent first)")
        if not rows:
            st.info("No saved outputs yet")
        else:
            # Filters
            all_tasks = ["All"] + sorted({r[1] for r in rows})
            task_filter = st.selectbox("Filter by task", options=all_tasks)
            search = st.text_input("Search saved outputs (matches task, input, or output)")

            # Apply filters
            filtered = []
            for rid, rtask, rinput, routput, created_at in rows:
                if task_filter != "All" and rtask != task_filter:
                    continue
                hay = f"{rid} {rtask} {rinput or ''} {routput or ''}".lower()
                if search and search.lower() not in hay:
                    continue
                filtered.append((rid, rtask, rinput, routput, created_at))

            if not filtered:
                st.info("No saved outputs match your filters")
            else:
                # Offer CSV export of filtered results
                sio = io.StringIO()
                writer = csv.writer(sio)
                writer.writerow(["id", "task", "input", "output", "created_at"])
                for row in filtered:
                    writer.writerow(row)
                csv_data = sio.getvalue()
                st.download_button("Export filtered CSV", csv_data, file_name="savannah_outputs.csv", mime="text/csv")

                for rid, rtask, rinput, routput, created_at in filtered:
                    with st.expander(f"{rid} — {rtask} — {created_at}"):
                        st.write("Input:")
                        st.write(rinput)
                        st.write("Output:")
                        st.write(routput)


if __name__ == "__main__":
    main()

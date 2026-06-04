# Savannah BBQ Growth Engine — MVP

Local Streamlit MVP to generate social copy for a Savannah food truck.

Quick start

1. Copy `.env.example` to `.env` and add your OpenAI API key:

```bash
cp .env.example .env
# then edit .env and set OPENAI_API_KEY
```

2. Install dependencies (prefer a virtualenv):

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

3. Run the app:

```bash
streamlit run app.py
```

Notes
- This is a local MVP. It does NOT connect to Facebook/Meta or run any automation.
- Keep your OpenAI key private; do not commit `.env` to version control.

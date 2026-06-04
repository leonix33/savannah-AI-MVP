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

## GitHub and deployment

- Initialize git if you haven't already:

```bash
git init
git add .
git commit -m "Initial Savannah BBQ Growth Engine MVP"
```

- To push to GitHub, create a new repository named `savannah-bbq-growth-engine` and follow the GitHub instructions to add a remote and push.

- This repo is now structured for deployment.

## Notes

- This is a local MVP. It does NOT connect to Facebook/Meta or run any automation.
- Keep your OpenAI key private; do not commit `.env` to version control.
- The `assets/` folder holds branding visuals for the app.

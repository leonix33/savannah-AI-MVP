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

## Meta read-only comment testing

The app can safely test read-only Facebook comment fetching before any real reply posting is enabled.

Add these values to your local `.env` file:

```bash
FACEBOOK_PAGE_ID=your_facebook_page_id_here
FACEBOOK_PAGE_ACCESS_TOKEN=your_page_access_token_here
FACEBOOK_GRAPH_VERSION=v20.0
LIVE_FACEBOOK_MODE=false
AUTO_PUBLISH_MODE=false
```

`FACEBOOK_PAGE_ID` is the numeric ID for the Savannah BBQ Facebook Page. You can find it in Meta Business tools, Page settings, or by using Meta Graph API tools while logged in as a Page admin.

`FACEBOOK_PAGE_ACCESS_TOKEN` is the Page access token generated from your Meta Developer App / Graph API Explorer. Keep this token private. Add it only to `.env`; do not paste it into code, screenshots, commits, or chat.

To get a real Facebook Post/Reel ID for testing, open the post or Reel on Facebook and copy its URL. The ID is usually visible in the URL, or you can use Graph API Explorer to list Page posts from the connected Page and copy the returned `id` value. A comment ID is returned when the app fetches real comments in the Comment Automation tab.

To test read-only comment fetching:

1. Make sure `.env` has `FACEBOOK_PAGE_ID`, `FACEBOOK_PAGE_ACCESS_TOKEN`, and `FACEBOOK_GRAPH_VERSION=v20.0`.
2. Keep `LIVE_FACEBOOK_MODE=false`.
3. Run the app with `streamlit run app.py`.
4. Open the `Comment Automation` tab.
5. Check the read-only Meta status indicators.
6. Click `Fetch Page Comments Read-Only`.
7. Confirm comments import into the local SQLite inbox.

This read-only flow does not post replies. Real reply posting must remain disabled until the approval workflow is tested with real comment IDs.

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

- This is a local MVP. Meta access is read-only for comment fetching unless future code explicitly enables approved live actions.
- Keep your OpenAI key private; do not commit `.env` to version control.
- The `assets/` folder holds branding visuals for the app.

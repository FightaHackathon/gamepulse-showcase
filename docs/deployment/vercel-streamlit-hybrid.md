# Vercel + Streamlit hybrid deployment

GamePulse uses two hosting surfaces:

1. Vercel serves the lightweight static landing page from `index.html` and
   `styles.css`.
2. Streamlit Community Cloud runs the interactive Python prototype from
   `app.py`.

The Vercel upload uses `.vercelignore` so raw datasets, processed CSVs, the
SQLite database and Python source are not sent to the static deployment. They
remain available in the GitHub repository through Git LFS.

## Deploy the interactive app

1. Push this repository to GitHub.
2. Open Streamlit Community Cloud and choose **Create app**.
3. Select the repository, branch `main`, and file `app.py`.
4. Add the variables from `.env.example` only when the corresponding provider
   credentials are available. Never upload `.env`.
5. Confirm the app starts in Demo mode and copy its `https://*.streamlit.app`
   URL.

The landing page defaults to `https://gamepulse-prototype.streamlit.app`. If
Streamlit assigns another URL, open the Vercel page with an `app` query value,
for example:

```text
https://<your-vercel-domain>/?app=https%3A%2F%2Fyour-app.streamlit.app
```

For a permanent link, replace the default URL in `index.html` and redeploy.

## Deploy the landing page

From the repository root, deploy the project through the Vercel connector or
Vercel CLI. Vercel detects `index.html`; `.vercelignore` keeps the deployment
small and static.

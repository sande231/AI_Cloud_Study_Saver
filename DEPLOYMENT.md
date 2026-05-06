# Deploy as a Website Link

The easiest way to make this Streamlit app open from a public website link is Streamlit Community Cloud.

## 1. Push this project to GitHub

Do not upload real secret files. Keep these ignored:

- `.env`
- `data/firebase_key.json`
- `.streamlit/secrets.toml`

## 2. Create the Streamlit app

1. Go to `https://share.streamlit.io`.
2. Choose your GitHub repository.
3. Set the main file path to:

```text
code/app.py
```

Streamlit uses the root `requirements.txt` in this repository.

## 3. Add Streamlit secrets

In the Streamlit app settings, open `Secrets` and add:

```toml
GROQ_API_KEY = "your_groq_api_key"
ADMIN_LOGIN_ID = "admin"
ADMIN_PASSWORD = "choose_a_strong_password"

[firebase_key]
type = "service_account"
project_id = "your_project_id"
private_key_id = "your_private_key_id"
private_key = "-----BEGIN PRIVATE KEY-----\nYOUR_KEY_HERE\n-----END PRIVATE KEY-----\n"
client_email = "firebase-adminsdk-xxxxx@your_project.iam.gserviceaccount.com"
client_id = "your_client_id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "your_client_cert_url"
universe_domain = "googleapis.com"
```

You can copy these values from your Firebase service account JSON file.

## 4. Open the link

After deployment finishes, Streamlit gives you a public URL. Anyone with the link can open the website, create a student account, log in, and use the app.

---

# Render.com Deployment

This app can also be hosted on Render as a Python web service.

## 1. Create a Render account

1. Go to `https://render.com`.
2. Sign in or create an account.
3. Connect your GitHub account.

## 2. Add this repository

1. Create a new Web Service.
2. Select the `AI_Cloud_Study_Saver` repository.
3. Choose branch `main`.

## 3. Use the following settings

- Environment: `Python 3`
- Build Command:

```bash
pip install -r requirements.txt
```

- Start Command:

```bash
streamlit run code/app.py --server.port $PORT
```

- Root directory: repository root

## 4. Configure Render environment variables

Set these environment variables in the Render dashboard:

- `GROQ_API_KEY`
- `ADMIN_LOGIN_ID`
- `ADMIN_PASSWORD`
- `FIREBASE_KEY_JSON`

If you prefer, you can also set `FIREBASE_KEY_JSON` from your service account file as a single JSON string.

## 5. Deploy and verify

Once the service is created, Render will build and deploy the app. Open the generated URL to verify the Streamlit app loads.

## 6. Custom domain

After Render has deployed the app, you can add a custom domain in the Render dashboard and configure DNS at your registrar.

---

# Custom Domain

To use a domain like `www.aistudysaver.com`:

1. Register the domain with a registrar.
2. In Streamlit Community Cloud or Render, add the custom domain.
3. Update DNS records as instructed by the host.
4. Enable HTTPS if not automatic.

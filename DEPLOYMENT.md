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

Streamlit will use the root `requirements.txt` added in this project.

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

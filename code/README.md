# AI Cloud Study Saver

AI Cloud Study Saver is a Streamlit web app for turning study notes into AI flashcards, saving study sessions in Firebase, and tracking student progress over time.

## Features

- Student sign up and login
- Admin login and monitoring dashboard
- PDF and TXT note upload
- Manual note paste box
- AI flashcard generation with Groq
- Firebase cloud storage for study sessions
- Progress report with study sessions, flashcards, words studied, strong cards, weak cards, and study streak
- Strong and weak area tracking based on flashcard mastery ratings
- Admin view for registered users, all sessions, and per-user progress

## Project Structure

```text
AI_Cloud_Study_Saver/
├── code/
│   ├── app.py
│   ├── requirements.txt
│   └── README.md
├── data/
│   └── firebase_key.json        # local only, ignored by Git
├── .streamlit/
│   └── config.toml
├── DEPLOYMENT.md
├── requirements.txt
└── README.md
```

## Local Setup

1. Create and activate a virtual environment.

```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies.

```bash
pip install -r requirements.txt
```

3. Add environment variables in `.env`.

```env
GROQ_API_KEY=your_groq_api_key
ADMIN_LOGIN_ID=admin
ADMIN_PASSWORD=sandy@123
```

4. Add your Firebase service account file locally.

```text
data/firebase_key.json
```

This file is ignored by Git and should not be uploaded publicly.

5. Run the app.

```bash
streamlit run code/app.py
```

Open:

```text
http://localhost:8501
```

## Admin Login

The local admin credentials are controlled by `.env`.

```text
Admin ID: admin
Password: sandy@123
```

Change the password before sharing or deploying the app.

## Deployment

For Streamlit Community Cloud or another hosted web link, see:

```text
DEPLOYMENT.md
```

The app supports hosted secrets through Streamlit secrets, so you do not need to upload `.env` or `firebase_key.json`.

## Security Notes

- Student passwords are stored as salted hashes.
- `.env`, Firebase credentials, virtual environment files, and Python cache files are ignored by Git.
- Admin credentials should be stored in environment variables or Streamlit secrets.

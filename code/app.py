import os
import json
import hashlib
import hmac
import re
from html import escape
import secrets
import streamlit as st
from datetime import datetime, timedelta

import firebase_admin
from firebase_admin import credentials, firestore

from dotenv import load_dotenv
from groq import Groq
import PyPDF2
import pandas as pd

# ---------------- Setup ----------------
load_dotenv()

st.set_page_config(
    page_title="AI Cloud Study Saver",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Register PWA (Progressive Web App)
def setup_pwa():
    # Inline service worker registration
    st.markdown(
        """
        <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
        <meta name="theme-color" content="#2563eb">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
        <meta name="apple-mobile-web-app-title" content="Study Saver">
        <meta name="description" content="AI-powered flashcard app for students. Generate, study, and track progress.">
        <link rel="manifest" href="/manifest.json">
        <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 192 192'><rect fill='%232563eb' width='192' height='192'/><text x='50%' y='50%' font-size='100' fill='white' text-anchor='middle' dominant-baseline='middle' font-weight='bold'>📚</text></svg>">
        <script>
            // Register Service Worker for offline support
            if ('serviceWorker' in navigator) {
                window.addEventListener('load', () => {
                    // Create inline service worker
                    const swCode = `
const CACHE_NAME = 'ai-study-saver-v1';
const urlsToCache = ['/', '/index.html'];

self.addEventListener('install', event => {
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    self.clients.claim();
});

self.addEventListener('fetch', event => {
    if (event.request.method !== 'GET') return;
    
    event.respondWith(
        fetch(event.request)
            .then(response => {
                const responseClone = response.clone();
                try {
                    caches.open(CACHE_NAME).then(cache => {
                        cache.put(event.request, responseClone);
                    });
                } catch(e) {}
                return response;
            })
            .catch(() => {
                return caches.match(event.request)
                    .then(response => response || new Response('Offline'));
            })
    );
});
`;
                    
                    const blob = new Blob([swCode], {type: 'application/javascript'});
                    const swUrl = URL.createObjectURL(blob);
                    
                    navigator.serviceWorker.register(swUrl)
                        .then(reg => console.log('✓ Service Worker registered'))
                        .catch(err => console.log('Service Worker registration failed:', err));
                });
            }
            
            // Handle install prompt for Android
            window.addEventListener('beforeinstallprompt', (e) => {
                e.preventDefault();
                window.deferredPrompt = e;
                window.showInstallPrompt = true;
            });
            
            // Show install button for Android/PWA-capable browsers
            if (window.matchMedia('(display-mode: standalone)').matches) {
                console.log('App is in standalone mode');
            }
        </script>
        """,
        unsafe_allow_html=True
    )

def get_secret(name, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def normalize_firebase_key(firebase_key):
    required_fields = ["type", "project_id", "private_key", "client_email"]
    missing_fields = [field for field in required_fields if not firebase_key.get(field)]

    if missing_fields:
        raise ValueError(f"Firebase key is missing: {', '.join(missing_fields)}")

    firebase_key["private_key"] = firebase_key.get("private_key", "").replace("\\n", "\n")
    return firebase_key


def parse_firebase_key_json(raw_value):
    raw_value = str(raw_value or "").strip()

    if not raw_value:
        raise ValueError("FIREBASE_KEY_JSON is empty.")

    if raw_value[0] in {"'", '"'} and raw_value[-1:] == raw_value[0]:
        raw_value = raw_value[1:-1].strip()

    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        pass

    # Render users sometimes paste JSON where the private_key contains real
    # line breaks instead of escaped \n sequences. Escape just that field.
    escaped_value = re.sub(
        r'("private_key"\s*:\s*")(.*?)(")',
        lambda match: match.group(1) + match.group(2).replace("\n", "\\n") + match.group(3),
        raw_value,
        flags=re.DOTALL,
    )
    return json.loads(escaped_value)


def get_firebase_credentials():
    firebase_key = get_secret("firebase_key")
    if firebase_key:
        firebase_key = normalize_firebase_key(dict(firebase_key))
        return credentials.Certificate(firebase_key)

    firebase_key_json = os.getenv("FIREBASE_KEY_JSON")
    if firebase_key_json:
        firebase_key = normalize_firebase_key(parse_firebase_key_json(firebase_key_json))
        return credentials.Certificate(firebase_key)

    return credentials.Certificate("data/firebase_key.json")


# Firebase
try:
    if not firebase_admin._apps:
        cred = get_firebase_credentials()
        firebase_admin.initialize_app(cred)

    db = firestore.client()
    FIREBASE_READY = True
    FIREBASE_ERROR = ""
except Exception as error:
    db = None
    FIREBASE_READY = False
    FIREBASE_ERROR = str(error)

# Groq
GROQ_API_KEY = get_secret("GROQ_API_KEY", os.getenv("GROQ_API_KEY"))
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

ADMIN_LOGIN_ID = get_secret("ADMIN_LOGIN_ID", os.getenv("ADMIN_LOGIN_ID", os.getenv("ADMIN_USERNAME", "admin")))
ADMIN_PASSWORD = get_secret("ADMIN_PASSWORD", os.getenv("ADMIN_PASSWORD", "admin123"))

# ---------------- Styling ----------------

def apply_app_styles():
    st.markdown(
        """
        <style>
            :root {
                --app-bg: #f6f8fb;
                --panel: #ffffff;
                --ink: #172033;
                --muted: #5d6778;
                --line: #e3e8f0;
                --blue: #2563eb;
                --green: #0f9f6e;
                --amber: #d97706;
                --rose: #e11d48;
            }

            .stApp {
                background:
                    linear-gradient(135deg, rgba(37, 99, 235, 0.08) 0%, rgba(15, 159, 110, 0.08) 34%, rgba(217, 119, 6, 0.06) 68%, rgba(225, 29, 72, 0.05) 100%),
                    linear-gradient(180deg, #f8fbff 0%, var(--app-bg) 42%, #ffffff 100%);
                color: var(--ink);
            }

            .block-container {
                padding-top: 1.7rem;
                padding-bottom: 3rem;
                max-width: 1180px;
            }

            [data-testid="stSidebar"] {
                background: #111827;
            }

            [data-testid="stSidebar"] * {
                color: #f8fafc;
            }

            h1, h2, h3 {
                letter-spacing: 0;
            }

            div[data-testid="stMetric"] {
                background: var(--panel);
                border: 1px solid var(--line);
                border-radius: 8px;
                padding: 1rem;
                box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
            }

            div[data-testid="stMetricLabel"] p {
                color: var(--muted);
                font-weight: 700;
            }

            .app-hero {
                border: 1px solid var(--line);
                background:
                    linear-gradient(135deg, rgba(17, 24, 39, 0.96) 0%, rgba(30, 64, 175, 0.92) 48%, rgba(15, 159, 110, 0.88) 100%);
                border-radius: 8px;
                padding: 1.65rem 1.65rem;
                box-shadow: 0 22px 46px rgba(15, 23, 42, 0.18);
                margin-bottom: 1.2rem;
                position: relative;
                overflow: hidden;
            }

            .app-hero:after {
                content: "";
                position: absolute;
                left: 0;
                right: 0;
                bottom: 0;
                height: 6px;
                background: linear-gradient(90deg, #38bdf8 0%, #22c55e 38%, #f59e0b 68%, #fb7185 100%);
            }

            .app-kicker {
                color: #bfdbfe;
                font-size: 0.82rem;
                font-weight: 800;
                text-transform: uppercase;
                margin-bottom: 0.35rem;
            }

            .app-hero h1 {
                margin: 0;
                font-size: clamp(2rem, 4vw, 3.4rem);
                line-height: 1.05;
                color: #ffffff;
            }

            .app-hero p {
                color: #dbeafe;
                font-size: 1.03rem;
                margin: 0.65rem 0 0;
                max-width: 780px;
            }

            .hero-dashboard {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 0.65rem;
                margin-top: 1.2rem;
                max-width: 860px;
            }

            .hero-stat {
                background: rgba(255, 255, 255, 0.12);
                border: 1px solid rgba(255, 255, 255, 0.22);
                border-radius: 8px;
                padding: 0.72rem;
            }

            .hero-stat b {
                display: block;
                color: #ffffff;
                font-size: 1.15rem;
            }

            .hero-stat span {
                color: #dbeafe;
                font-size: 0.8rem;
            }

            .info-grid {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 0.85rem;
                margin: 0.75rem 0 1.1rem;
            }

            .info-card {
                background: var(--panel);
                border: 1px solid var(--line);
                border-radius: 8px;
                padding: 1rem;
                min-height: 142px;
                box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
                position: relative;
                overflow: hidden;
            }

            .info-card:before {
                content: "";
                position: absolute;
                left: 0;
                top: 0;
                bottom: 0;
                width: 5px;
                background: var(--accent, var(--blue));
            }

            .info-card.blue { --accent: #2563eb; }
            .info-card.green { --accent: #0f9f6e; }
            .info-card.amber { --accent: #d97706; }
            .info-card.rose { --accent: #e11d48; }

            .info-card strong {
                display: block;
                color: var(--ink);
                font-size: 1rem;
                margin-bottom: 0.35rem;
            }

            .info-card span {
                color: var(--muted);
                font-size: 0.93rem;
            }

            .note-strip {
                background: #fffaf0;
                border: 1px solid #fde7bd;
                border-radius: 8px;
                color: #6f4d10;
                padding: 0.85rem 1rem;
                margin: 0.5rem 0 1rem;
            }

            .section-band {
                background: var(--panel);
                border: 1px solid var(--line);
                border-radius: 8px;
                padding: 1rem;
                margin-bottom: 1rem;
                box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
            }

            .section-band h3 {
                margin-top: 0;
            }

            .section-band p {
                color: var(--muted);
                margin-bottom: 0;
            }

            .dashboard-grid {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 0.8rem;
                margin: 0.75rem 0 1rem;
            }

            .dashboard-tile {
                background: var(--panel);
                border: 1px solid var(--line);
                border-radius: 8px;
                padding: 0.95rem;
                box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
                border-top: 5px solid var(--accent, var(--blue));
            }

            .dashboard-tile b {
                display: block;
                font-size: 1.55rem;
                line-height: 1;
                color: var(--ink);
            }

            .dashboard-tile span {
                color: var(--muted);
                font-size: 0.88rem;
                font-weight: 700;
            }

            .workflow-strip {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 0.65rem;
                margin-bottom: 1rem;
            }

            .workflow-step {
                background: #ffffff;
                border: 1px solid var(--line);
                border-radius: 8px;
                padding: 0.8rem;
            }

            .workflow-step b {
                color: var(--ink);
                display: block;
                margin-bottom: 0.18rem;
            }

            .workflow-step span {
                color: var(--muted);
                font-size: 0.86rem;
            }

            .coach-grid {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 0.8rem;
                margin: 0.75rem 0 1rem;
            }

            .coach-card {
                background: #ffffff;
                border: 1px solid var(--line);
                border-radius: 8px;
                padding: 0.95rem;
                box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
                border-left: 5px solid var(--accent, var(--blue));
            }

            .coach-card b {
                display: block;
                color: var(--ink);
                margin-bottom: 0.25rem;
            }

            .coach-card span {
                color: var(--muted);
                font-size: 0.9rem;
            }

            .pill-row {
                display: flex;
                flex-wrap: wrap;
                gap: 0.5rem;
                margin-top: 0.8rem;
            }

            .pill {
                background: #eef2ff;
                color: #243b7a;
                border: 1px solid #d8e0ff;
                border-radius: 999px;
                font-size: 0.84rem;
                font-weight: 700;
                padding: 0.32rem 0.65rem;
            }

            div[data-baseweb="tab-list"] {
                gap: 0.35rem;
            }

            button[data-baseweb="tab"] {
                background: #ffffff;
                border: 1px solid var(--line);
                border-radius: 8px;
                padding: 0.45rem 0.8rem;
            }

            .stButton > button,
            .stFormSubmitButton > button {
                border-radius: 8px;
                border: 1px solid #1d4ed8;
                background: #2563eb;
                color: #ffffff;
                font-weight: 800;
            }

            .stButton > button:hover,
            .stFormSubmitButton > button:hover {
                border-color: #1e40af;
                background: #1d4ed8;
                color: #ffffff;
            }

            @media (max-width: 780px) {
                .info-grid,
                .hero-dashboard,
                .dashboard-grid,
                .workflow-strip,
                .coach-grid {
                    grid-template-columns: 1fr;
                }

                .app-hero {
                    padding: 1rem;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def show_app_header():
    st.markdown(
        """
        <div class="app-hero">
            <div class="app-kicker">AI-powered study workspace</div>
            <h1>AI Cloud Study Saver</h1>
            <p>Turn class notes into focused flashcards, save every study session in the cloud, and track which topics are strong, weak, or ready for review.</p>
            <div class="pill-row">
                <span class="pill">PDF and TXT notes</span>
                <span class="pill">AI flashcards</span>
                <span class="pill">Cloud history</span>
                <span class="pill">Progress reports</span>
            </div>
            <div class="hero-dashboard">
                <div class="hero-stat"><b>Upload</b><span>notes from class</span></div>
                <div class="hero-stat"><b>Generate</b><span>AI flashcards</span></div>
                <div class="hero-stat"><b>Rate</b><span>Strong, Review, Weak</span></div>
                <div class="hero-stat"><b>Improve</b><span>with progress data</span></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_login_overview():
    st.markdown(
        """
        <div class="info-grid">
            <div class="info-card blue">
                <strong>1. Add your study material</strong>
                <span>Upload a PDF, upload a text file, or paste notes from class. Keep the content focused for better flashcards.</span>
            </div>
            <div class="info-card green">
                <strong>2. Generate smart flashcards</strong>
                <span>The app finds key terms and definitions, then creates cards you can rate as Strong, Review, or Weak.</span>
            </div>
            <div class="info-card amber">
                <strong>3. Save and track growth</strong>
                <span>Each saved session builds your progress report so you know what to study next instead of guessing.</span>
            </div>
        </div>
        <div class="workflow-strip">
            <div class="workflow-step"><b>Best for</b><span>lecture notes, exam review, chapter summaries, and quick revision.</span></div>
            <div class="workflow-step"><b>Study smarter</b><span>Weak cards show where to spend your next 10 minutes.</span></div>
            <div class="workflow-step"><b>Cloud saved</b><span>Your sessions stay connected to your login account.</span></div>
            <div class="workflow-step"><b>Teacher view</b><span>Admins can see class progress and common weak areas.</span></div>
        </div>
        <div class="note-strip">
            <strong>Important:</strong> Create a student account before saving sessions. Use the same login every time so your progress report stays connected.
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_student_intro(user):
    display_name = escape(str(user.get("display_name", "Student")))
    st.markdown(
        f"""
        <div class="section-band">
            <h3>Welcome back, {display_name}</h3>
            <p>Start with one chapter, lecture, or topic. Generate flashcards, rate each card honestly, then save the session to update your progress report.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_admin_intro():
    st.markdown(
        """
        <div class="section-band">
            <h3>Admin Dashboard</h3>
            <p>Monitor student accounts, saved study sessions, flashcard volume, and weak areas across the class.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_dashboard_tiles(tiles):
    tile_html = []
    for value, label, color in tiles:
        tile_html.append(
            f"""
            <div class="dashboard-tile" style="--accent: {color};">
                <b>{escape(str(value))}</b>
                <span>{escape(str(label))}</span>
            </div>
            """
        )

    st.markdown(
        f"""<div class="dashboard-grid">{''.join(tile_html)}</div>""",
        unsafe_allow_html=True,
    )


def show_student_snapshot(docs):
    session_df, _ = build_progress_report(docs)

    if session_df.empty:
        render_dashboard_tiles([
            ("0", "Saved sessions", "#2563eb"),
            ("0", "Flashcards created", "#0f9f6e"),
            ("0 day", "Study streak", "#f59e0b"),
            ("0", "Weak cards to review", "#e11d48"),
        ])
        return

    total_sessions = len(session_df)
    total_cards = int(session_df["Flashcards"].sum())
    streak = get_study_streak(session_df)
    weak_cards = int(session_df["Weak"].sum())

    streak_label = f"{streak} day" if streak == 1 else f"{streak} days"
    render_dashboard_tiles([
        (total_sessions, "Saved sessions", "#2563eb"),
        (total_cards, "Flashcards created", "#0f9f6e"),
        (streak_label, "Study streak", "#f59e0b"),
        (weak_cards, "Weak cards to review", "#e11d48"),
    ])


def show_admin_snapshot(user_rows, session_df):
    total_sessions = len(session_df)
    total_cards = int(session_df["Flashcards"].sum()) if not session_df.empty else 0
    weak_cards = int(session_df["Weak"].sum()) if not session_df.empty else 0

    render_dashboard_tiles([
        (len(user_rows), "Registered users", "#2563eb"),
        (total_sessions, "Study sessions", "#0f9f6e"),
        (total_cards, "Flashcards saved", "#d97706"),
        (weak_cards, "Weak cards flagged", "#e11d48"),
    ])

# ---------------- Functions ----------------

def normalize_login_id(login_id):
    return str(login_id or "").strip().lower()


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        str(password).encode("utf-8"),
        salt.encode("utf-8"),
        120000,
    ).hex()
    return f"{salt}:{password_hash}"


def verify_password(password, stored_hash):
    try:
        salt, expected_hash = str(stored_hash).split(":", 1)
    except ValueError:
        return False

    actual_hash = hash_password(password, salt).split(":", 1)[1]
    return hmac.compare_digest(actual_hash, expected_hash)


def get_user_ref(login_id):
    return db.collection("users").document(normalize_login_id(login_id))


def create_student_account(login_id, password, display_name):
    login_id = normalize_login_id(login_id)
    display_name = str(display_name or "").strip()

    if not login_id or not password or not display_name:
        return False, "Enter login ID, password, and name."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    if login_id == normalize_login_id(ADMIN_LOGIN_ID):
        return False, "That login ID is reserved for admin."

    user_ref = get_user_ref(login_id)
    if user_ref.get().exists:
        return False, "That login ID already exists."

    user_ref.set({
        "login_id": login_id,
        "display_name": display_name,
        "password_hash": hash_password(password),
        "role": "student",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    return True, "Account created. You can log in now."


def authenticate_student(login_id, password):
    login_id = normalize_login_id(login_id)
    user_doc = get_user_ref(login_id).get()

    if not user_doc.exists:
        return None

    user = user_doc.to_dict()
    if user.get("role") != "student":
        return None
    if not verify_password(password, user.get("password_hash", "")):
        return None

    return {
        "login_id": login_id,
        "display_name": user.get("display_name", login_id),
        "role": "student",
    }


def authenticate_admin(login_id, password):
    if normalize_login_id(login_id) != normalize_login_id(ADMIN_LOGIN_ID):
        return None
    if not hmac.compare_digest(str(password), str(ADMIN_PASSWORD)):
        return None

    return {
        "login_id": normalize_login_id(ADMIN_LOGIN_ID),
        "display_name": "Admin",
        "role": "admin",
    }


def login_user(user):
    st.session_state["auth_user"] = user
    st.session_state.pop("flashcards", None)
    st.session_state.pop("mastery", None)


def logout_user():
    for key in ["auth_user", "flashcards", "mastery", "save_success"]:
        st.session_state.pop(key, None)


def get_current_user():
    return st.session_state.get("auth_user")

def extract_text_from_pdf(file):
    pdf_reader = PyPDF2.PdfReader(file)
    text = ""
    for page in pdf_reader.pages:
        text += (page.extract_text() or "") + "\n"
    return text.strip()


def parse_flashcard_response(content):
    content = str(content or "").strip()
    if content.startswith("```"):
        content = content.strip("`").strip()
        if content.lower().startswith("json"):
            content = content[4:].strip()

    start = content.find("[")
    end = content.rfind("]")
    if start != -1 and end != -1:
        content = content[start:end + 1]

    cards = json.loads(content)
    if not isinstance(cards, list):
        return []

    cleaned_cards = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        term = str(card.get("term", "")).strip()
        definition = str(card.get("definition", "")).strip()
        if term and definition:
            cleaned_cards.append({"term": term, "definition": definition})

    return cleaned_cards


def generate_flashcards(text):
    if client is None:
        st.error("Missing GROQ_API_KEY")
        return []

    prompt = f"""
Create 5 flashcards from these notes.

Each flashcard must have:
- term
- definition

Return ONLY JSON:
[{{"term":"...","definition":"..."}}]

Notes:
{text}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )

        return parse_flashcard_response(response.choices[0].message.content)

    except Exception as e:
        st.error(f"AI error: {e}")
        return []


def save_to_cloud(name, notes, flashcards):
    user = get_current_user() or {}
    flashcards = flashcards or []
    mastery = st.session_state.get("mastery", {})
    db.collection("study_notes").add({
        "user_id": normalize_login_id(user.get("login_id", name)),
        "student_name": str(name or "").strip(),
        "notes": str(notes or "").strip(),
        "flashcards": flashcards,
        "mastery": {
            str(index): mastery.get(str(index), "Not rated")
            for index in range(len(flashcards))
        },
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


def get_notes():
    return list(db.collection("study_notes").stream())


def get_notes_for_user(login_id):
    login_id = normalize_login_id(login_id)
    return list(db.collection("study_notes").where("user_id", "==", login_id).stream())


def get_users():
    return list(db.collection("users").stream())


def parse_created_at(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


def count_words(text):
    return len(str(text or "").split())


def get_card_topic(card):
    term = str(card.get("term", "General")).strip()
    return term[:45] if term else "General"


def get_mastery_score(value):
    scores = {
        "Strong": 100,
        "Review": 60,
        "Weak": 25,
        "Not rated": 0,
    }
    return scores.get(value, 0)


def build_progress_report(docs):
    sessions = []
    area_scores = {}

    for doc in docs:
        item = doc.to_dict()
        flashcards = item.get("flashcards", []) or []
        mastery = item.get("mastery", {}) or {}
        created_at = parse_created_at(item.get("created_at"))

        sessions.append({
            "User ID": item.get("user_id", ""),
            "Student": item.get("student_name", "Unknown"),
            "Date": created_at,
            "Words": count_words(item.get("notes")),
            "Flashcards": len(flashcards),
            "Strong": sum(1 for value in mastery.values() if value == "Strong"),
            "Review": sum(1 for value in mastery.values() if value == "Review"),
            "Weak": sum(1 for value in mastery.values() if value == "Weak"),
        })

        for index, card in enumerate(flashcards):
            topic = get_card_topic(card)
            rating = mastery.get(str(index), "Not rated")
            area_scores.setdefault(topic, []).append(get_mastery_score(rating))

    session_df = pd.DataFrame(sessions)

    areas = []
    for topic, scores in area_scores.items():
        average = round(sum(scores) / len(scores)) if scores else 0
        if average >= 75:
            status = "Strong"
        elif average >= 45:
            status = "Needs review"
        else:
            status = "Weak"
        areas.append({
            "Area": topic,
            "Score": average,
            "Status": status,
            "Cards": len(scores),
        })

    area_df = pd.DataFrame(areas).sort_values(
        by=["Score", "Cards"],
        ascending=[False, False],
    ) if areas else pd.DataFrame(columns=["Area", "Score", "Status", "Cards"])

    return session_df, area_df


def get_study_streak(session_df):
    if session_df.empty or "Date" not in session_df:
        return 0

    dates = {
        value.date()
        for value in session_df["Date"].dropna()
        if isinstance(value, datetime)
    }
    if not dates:
        return 0

    streak = 0
    cursor = max(dates)
    while cursor in dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def get_mastery_breakdown(session_df):
    if session_df.empty:
        return pd.DataFrame(columns=["Status", "Cards", "Color"])

    strong_cards = int(session_df["Strong"].sum())
    review_cards = int(session_df["Review"].sum())
    weak_cards = int(session_df["Weak"].sum())
    total_cards = int(session_df["Flashcards"].sum())
    rated_cards = strong_cards + review_cards + weak_cards
    not_rated = max(total_cards - rated_cards, 0)

    rows = [
        {"Status": "Strong", "Cards": strong_cards, "Color": "#0f9f6e"},
        {"Status": "Review", "Cards": review_cards, "Color": "#d97706"},
        {"Status": "Weak", "Cards": weak_cards, "Color": "#e11d48"},
        {"Status": "Not rated", "Cards": not_rated, "Color": "#64748b"},
    ]
    return pd.DataFrame([row for row in rows if row["Cards"] > 0])


def show_mastery_pie_chart(session_df):
    pie_df = get_mastery_breakdown(session_df)

    if pie_df.empty:
        st.info("Rate and save flashcards to unlock your mastery chart.")
        return

    st.vega_lite_chart(
        pie_df,
        {
            "mark": {"type": "arc", "innerRadius": 70, "outerRadius": 125, "cornerRadius": 4},
            "encoding": {
                "theta": {"field": "Cards", "type": "quantitative"},
                "color": {
                    "field": "Status",
                    "type": "nominal",
                    "scale": {
                        "domain": ["Strong", "Review", "Weak", "Not rated"],
                        "range": ["#0f9f6e", "#d97706", "#e11d48", "#64748b"],
                    },
                    "legend": {"orient": "bottom", "title": None},
                },
                "tooltip": [
                    {"field": "Status", "type": "nominal"},
                    {"field": "Cards", "type": "quantitative"},
                ],
            },
            "view": {"stroke": None},
        },
        use_container_width=True,
    )


def show_study_coach(session_df, area_df):
    total_cards = int(session_df["Flashcards"].sum()) if not session_df.empty else 0
    strong_cards = int(session_df["Strong"].sum()) if not session_df.empty else 0
    weak_cards = int(session_df["Weak"].sum()) if not session_df.empty else 0
    review_cards = int(session_df["Review"].sum()) if not session_df.empty else 0

    mastery_percent = round((strong_cards / total_cards) * 100) if total_cards else 0
    focus_area = "Rate more cards"
    focus_detail = "After saving ratings, your weakest topic will appear here."

    if not area_df.empty:
        weakest = area_df.sort_values(by=["Score", "Cards"], ascending=[True, False]).iloc[0]
        focus_area = str(weakest["Area"])
        focus_detail = f"Current score: {int(weakest['Score'])}%. Review this first."

    if weak_cards:
        next_action = f"Review {weak_cards} weak card(s) before generating new ones."
    elif review_cards:
        next_action = f"Practice {review_cards} review card(s) until they feel strong."
    else:
        next_action = "Generate a fresh set of flashcards and rate them after studying."

    st.markdown(
        f"""
        <div class="coach-grid">
            <div class="coach-card" style="--accent: #0f9f6e;">
                <b>{mastery_percent}% mastery</b>
                <span>Percent of saved cards marked Strong.</span>
            </div>
            <div class="coach-card" style="--accent: #e11d48;">
                <b>{escape(focus_area)}</b>
                <span>{escape(focus_detail)}</span>
            </div>
            <div class="coach-card" style="--accent: #2563eb;">
                <b>Next best move</b>
                <span>{escape(next_action)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_progress_report(docs):
    st.subheader("📈 Progress Report")

    session_df, area_df = build_progress_report(docs)

    if session_df.empty:
        st.info("Save a study session to unlock your progress report.")
        return

    total_sessions = len(session_df)
    total_cards = int(session_df["Flashcards"].sum())
    total_words = int(session_df["Words"].sum())
    strong_cards = int(session_df["Strong"].sum())
    weak_cards = int(session_df["Weak"].sum())
    streak = get_study_streak(session_df)

    metric_cols = st.columns(5)
    metric_cols[0].metric("Study Sessions", total_sessions)
    metric_cols[1].metric("Flashcards", total_cards)
    metric_cols[2].metric("Words Studied", total_words)
    metric_cols[3].metric("Strong Cards", strong_cards)
    metric_cols[4].metric("Study Streak", f"{streak} day" if streak == 1 else f"{streak} days")

    show_study_coach(session_df, area_df)

    if weak_cards:
        st.warning(f"You marked {weak_cards} card(s) as weak. Start there for the fastest improvement.")
    elif strong_cards:
        st.success("Nice work. Your latest ratings show no weak cards yet.")
    else:
        st.info("Rate your flashcards after generating them to see strong and weak areas.")

    chart_df = session_df.dropna(subset=["Date"]).copy()
    chart_col, pie_col = st.columns([1.25, 1])
    with chart_col:
        st.write("Study activity")
        if not chart_df.empty:
            chart_df["Study Date"] = chart_df["Date"].dt.date
            daily_df = chart_df.groupby("Study Date", as_index=False)[["Flashcards", "Words"]].sum()
            st.line_chart(daily_df, x="Study Date", y=["Flashcards", "Words"])
        else:
            st.info("Save dated sessions to see study activity over time.")

    with pie_col:
        st.write("Mastery breakdown")
        show_mastery_pie_chart(session_df)

    if not area_df.empty:
        strong_areas = area_df[area_df["Status"] == "Strong"].head(5)
        weak_areas = area_df[area_df["Status"] == "Weak"].sort_values(
            by=["Score", "Cards"],
            ascending=[True, False],
        ).head(5)

        col1, col2 = st.columns(2)
        with col1:
            st.write("Strong areas")
            if strong_areas.empty:
                st.caption("Rate more cards as Strong to build this list.")
            else:
                for _, row in strong_areas.iterrows():
                    st.progress(row["Score"] / 100, text=f"{row['Area']} - {row['Score']}%")

        with col2:
            st.write("Weak areas")
            if weak_areas.empty:
                st.caption("No weak areas yet.")
            else:
                for _, row in weak_areas.iterrows():
                    st.progress(row["Score"] / 100, text=f"{row['Area']} - {row['Score']}%")

        st.write("All topic scores")
        st.dataframe(area_df, width="stretch", hide_index=True)


# ---------------- UI ----------------

setup_pwa()
apply_app_styles()
show_app_header()

if not FIREBASE_READY:
    st.error("Firebase is not configured correctly.")
    st.info(
        "On Render, set FIREBASE_KEY_JSON to the full Firebase service account JSON. "
        "Locally, keep the JSON file at data/firebase_key.json."
    )
    st.caption(f"Configuration detail: {FIREBASE_ERROR}")
    st.stop()


def show_login_screen():
    show_login_overview()
    st.subheader("Choose how to continue")

    login_tab, signup_tab, admin_tab = st.tabs(["Student Login", "Create Account", "Admin Login"])

    with login_tab:
        st.caption("Use your student login to continue studying and see your saved progress.")
        with st.form("student_login_form"):
            login_id = st.text_input("Login ID", key="student_login_id")
            password = st.text_input("Password", type="password", key="student_login_password")
            submitted = st.form_submit_button("Login")

        if submitted:
            user = authenticate_student(login_id, password)
            if user:
                login_user(user)
                st.success("Logged in successfully.")
                st.rerun()
            else:
                st.error("Invalid student login ID or password.")

    with signup_tab:
        st.caption("New here? Create one student account, then use it every time you save notes.")
        with st.form("student_signup_form"):
            display_name = st.text_input("Student Name")
            login_id = st.text_input("Choose Login ID")
            password = st.text_input("Choose Password", type="password")
            submitted = st.form_submit_button("Create Account")

        if submitted:
            created, message = create_student_account(login_id, password, display_name)
            if created:
                st.success(message)
            else:
                st.error(message)

    with admin_tab:
        st.caption("Admin access is for reviewing student activity and class-wide weak areas.")
        with st.form("admin_login_form"):
            login_id = st.text_input("Admin Login ID")
            password = st.text_input("Admin Password", type="password")
            submitted = st.form_submit_button("Admin Login")

        if submitted:
            user = authenticate_admin(login_id, password)
            if user:
                login_user(user)
                st.success("Admin logged in successfully.")
                st.rerun()
            else:
                st.error("Invalid admin login ID or password.")

        if ADMIN_LOGIN_ID == "admin" and ADMIN_PASSWORD == "admin123":
            st.warning("Default admin login is active. Set ADMIN_LOGIN_ID and ADMIN_PASSWORD in .env before sharing this app.")


def show_saved_sessions(docs):
    st.subheader("📚 Saved Sessions")

    if not docs:
        st.info("No saved sessions yet.")
        return

    search_query = st.text_input("🔍 Search sessions by name or date", key="session_search").lower().strip()

    filtered_docs = []
    for doc in docs:
        item = doc.to_dict()
        student_name = str(item.get("student_name", "")).lower()
        created_at = str(item.get("created_at", "")).lower()
        if search_query in student_name or search_query in created_at:
            filtered_docs.append(doc)

    if search_query and not filtered_docs:
        st.warning(f"No sessions found matching '{search_query}'.")
        return

    for doc in sorted(filtered_docs, key=lambda item: item.to_dict().get("created_at", ""), reverse=True):
        item = doc.to_dict()
        flashcards = item.get("flashcards", []) or []
        mastery = item.get("mastery", {}) or {}
        title = f"{item.get('student_name')} - {item.get('created_at')}"

        with st.expander(title):
            st.caption(f"Login ID: {item.get('user_id', 'unknown')}")
            st.write(item.get("notes"))

            st.write("Flashcards:")
            for index, card in enumerate(flashcards):
                rating = mastery.get(str(index), "Not rated")
                st.write(f"- {card.get('term')}: {card.get('definition')} ({rating})")


def show_pwa_install_prompt():
    st.sidebar.markdown(
        """
        <div style="background: #e0f2fe; border: 1px solid #0284c7; border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
            <p style="margin: 0 0 0.5rem 0; font-weight: bold; color: #0c4a6e;">📱 Install App</p>
            <p style="margin: 0 0 0.75rem 0; font-size: 0.9rem; color: #0c4a6e;">Get offline access and quick launch from your home screen.</p>
            <button id="install-app-btn" style="display: none; width: 100%; background: #0284c7; color: white; border: none; border-radius: 6px; padding: 0.5rem; font-weight: bold; cursor: pointer;">Install Now</button>
        </div>
        <script>
            const installBtn = document.getElementById('install-app-btn');
            if (installBtn && window.deferredPrompt) {
                installBtn.style.display = 'block';
                installBtn.addEventListener('click', async () => {
                    if (window.deferredPrompt) {
                        window.deferredPrompt.prompt();
                        const { outcome } = await window.deferredPrompt.userChoice;
                        console.log(`User response to the install prompt: ${outcome}`);
                        window.deferredPrompt = null;
                    }
                });
            }
        </script>
        """,
        unsafe_allow_html=True
    )


def show_student_app(user):
    st.sidebar.success(f"Logged in as {user['display_name']}")
    if st.sidebar.button("Logout"):
        logout_user()
        st.rerun()
    
    show_pwa_install_prompt()

    if st.session_state.pop("save_success", False):
        st.success("Saved to Firebase.")

    show_student_intro(user)
    student_docs = get_notes_for_user(user["login_id"])
    show_student_snapshot(student_docs)

    tab_study, tab_progress, tab_saved = st.tabs(["Study", "Progress Report", "Saved Sessions"])

    with tab_study:
        st.markdown(
            """
            <div class="section-band">
                <h3>Create a study session</h3>
                <p>Add notes, generate cards, then save after rating them. Short, topic-focused notes usually create the best flashcards.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        name = st.text_input("Student Name", value=user["display_name"])
        uploaded_file = st.file_uploader("Upload PDF or TXT", type=["pdf", "txt"])
        manual_notes = st.text_area("Or paste notes manually", height=200)

        notes = ""

        if uploaded_file:
            if uploaded_file.type == "application/pdf":
                notes = extract_text_from_pdf(uploaded_file)
                st.success("PDF uploaded successfully!")

            elif uploaded_file.type == "text/plain":
                notes = uploaded_file.read().decode("utf-8")
                st.success("Text file uploaded successfully!")

        else:
            notes = manual_notes

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("Generate AI Flashcards"):
                if notes.strip():
                    with st.spinner("Generating flashcards..."):
                        flashcards = generate_flashcards(notes)
                        st.session_state["flashcards"] = flashcards
                        st.session_state["mastery"] = {}
                        st.success("Flashcards ready!")
                else:
                    st.warning("Add notes first.")

        with col2:
            if st.button("🔄 Regenerate", help="Create a new set of flashcards from the same notes"):
                if notes.strip():
                    with st.spinner("Regenerating flashcards..."):
                        flashcards = generate_flashcards(notes)
                        st.session_state["flashcards"] = flashcards
                        st.session_state["mastery"] = {}
                        st.success("New flashcards generated!")
                else:
                    st.warning("Add notes first.")

        with col3:
            if st.button("Save to Cloud"):
                if name and notes.strip():
                    save_to_cloud(name, notes, st.session_state.get("flashcards", []))
                    st.session_state["save_success"] = True
                    st.rerun()
                else:
                    st.warning("Enter name and notes.")

        if "flashcards" in st.session_state:
            st.subheader("🧠 Flashcards")
            st.caption("Rate each card before saving so the progress report can find your strong and weak areas.")

            search_cards = st.text_input("🔍 Search flashcards", key="flashcard_search").lower().strip()

            mastery = st.session_state.setdefault("mastery", {})

            filtered_indices = []
            for index, card in enumerate(st.session_state["flashcards"]):
                term = str(card.get("term", "")).lower()
                definition = str(card.get("definition", "")).lower()
                if search_cards in term or search_cards in definition:
                    filtered_indices.append(index)

            if search_cards and not filtered_indices:
                st.warning(f"No flashcards match '{search_cards}'.")
            else:
                for index in filtered_indices:
                    card = st.session_state["flashcards"][index]
                    with st.container(border=True):
                        st.markdown(f"**{card.get('term')}**")
                        st.write(card.get("definition"))
                        mastery[str(index)] = st.radio(
                            "How well do you know this?",
                            ["Strong", "Review", "Weak"],
                            horizontal=True,
                            key=f"mastery_{index}",
                            index=["Strong", "Review", "Weak"].index(mastery.get(str(index), "Review"))
                            if mastery.get(str(index), "Review") in ["Strong", "Review", "Weak"]
                            else 1,
                        )

    with tab_progress:
        show_progress_report(student_docs)

    with tab_saved:
        show_saved_sessions(student_docs)


def show_admin_app(user):
    st.sidebar.success(f"Logged in as {user['display_name']}")
    if st.sidebar.button("Logout"):
        logout_user()
        st.rerun()

    show_admin_intro()

    users = get_users()
    docs = get_notes()

    user_rows = []
    for user_doc in users:
        item = user_doc.to_dict()
        user_rows.append({
            "Login ID": item.get("login_id", user_doc.id),
            "Name": item.get("display_name", ""),
            "Role": item.get("role", ""),
            "Created At": item.get("created_at", ""),
        })

    session_df, area_df = build_progress_report(docs)
    show_admin_snapshot(user_rows, session_df)

    admin_tab_users, admin_tab_progress, admin_tab_sessions = st.tabs(["Users", "Progress", "Sessions"])

    with admin_tab_users:
        st.write("Registered students")
        if user_rows:
            st.dataframe(pd.DataFrame(user_rows), width="stretch", hide_index=True)
        else:
            st.info("No student users yet.")

    with admin_tab_progress:
        show_progress_report(docs)

        if not session_df.empty:
            st.write("Progress by user")
            by_user = session_df.groupby(["User ID", "Student"], as_index=False)[
                ["Words", "Flashcards", "Strong", "Review", "Weak"]
            ].sum()
            st.dataframe(by_user, width="stretch", hide_index=True)

        if not area_df.empty:
            st.write("Overall strong and weak areas")
            st.dataframe(area_df, width="stretch", hide_index=True)

    with admin_tab_sessions:
        show_saved_sessions(docs)


current_user = get_current_user()

if not current_user:
    show_login_screen()
elif current_user["role"] == "admin":
    show_admin_app(current_user)
else:
    show_student_app(current_user)

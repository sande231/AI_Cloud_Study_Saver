import os
import json
import hashlib
import hmac
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

st.set_page_config(page_title="AI Cloud Study Saver", layout="wide")

def get_secret(name, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def get_firebase_credentials():
    firebase_key = get_secret("firebase_key")
    if firebase_key:
        firebase_key = dict(firebase_key)
        firebase_key["private_key"] = firebase_key.get("private_key", "").replace("\\n", "\n")
        return credentials.Certificate(firebase_key)

    firebase_key_json = os.getenv("FIREBASE_KEY_JSON")
    if firebase_key_json:
        firebase_key = json.loads(firebase_key_json)
        firebase_key["private_key"] = firebase_key.get("private_key", "").replace("\\n", "\n")
        return credentials.Certificate(firebase_key)

    return credentials.Certificate("data/firebase_key.json")


# Firebase
if not firebase_admin._apps:
    cred = get_firebase_credentials()
    firebase_admin.initialize_app(cred)

db = firestore.client()

# Groq
GROQ_API_KEY = get_secret("GROQ_API_KEY", os.getenv("GROQ_API_KEY"))
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

ADMIN_LOGIN_ID = get_secret("ADMIN_LOGIN_ID", os.getenv("ADMIN_LOGIN_ID", os.getenv("ADMIN_USERNAME", "admin")))
ADMIN_PASSWORD = get_secret("ADMIN_PASSWORD", os.getenv("ADMIN_PASSWORD", "admin123"))

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
    for key in ["auth_user", "flashcards", "mastery"]:
        st.session_state.pop(key, None)


def get_current_user():
    return st.session_state.get("auth_user")

def extract_text_from_pdf(file):
    pdf_reader = PyPDF2.PdfReader(file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n"
    return text


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

        return json.loads(response.choices[0].message.content)

    except Exception as e:
        st.error(f"AI error: {e}")
        return []


def save_to_cloud(name, notes, flashcards):
    user = get_current_user() or {}
    db.collection("study_notes").add({
        "user_id": user.get("login_id", normalize_login_id(name)),
        "student_name": name,
        "notes": notes,
        "flashcards": flashcards,
        "mastery": st.session_state.get("mastery", {}),
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

    if weak_cards:
        st.warning(f"You marked {weak_cards} card(s) as weak. Start there for the fastest improvement.")
    elif strong_cards:
        st.success("Nice work. Your latest ratings show no weak cards yet.")
    else:
        st.info("Rate your flashcards after generating them to see strong and weak areas.")

    chart_df = session_df.dropna(subset=["Date"]).copy()
    if not chart_df.empty:
        chart_df["Study Date"] = chart_df["Date"].dt.date
        daily_df = chart_df.groupby("Study Date", as_index=False)[["Flashcards", "Words"]].sum()
        st.write("Study activity")
        st.line_chart(daily_df, x="Study Date", y=["Flashcards", "Words"])

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

st.title("☁️ AI Cloud Study Saver")

st.write("Upload notes, generate AI flashcards, save them in cloud, and track what you are strong or weak in.")


def show_login_screen():
    st.subheader("Login")

    login_tab, signup_tab, admin_tab = st.tabs(["Student Login", "Create Account", "Admin Login"])

    with login_tab:
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

    for doc in docs:
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


def show_student_app(user):
    st.sidebar.success(f"Logged in as {user['display_name']}")
    if st.sidebar.button("Logout"):
        logout_user()
        st.rerun()

    tab_study, tab_progress, tab_saved = st.tabs(["Study", "Progress Report", "Saved Sessions"])

    with tab_study:
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

        col1, col2 = st.columns(2)

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
            if st.button("Save to Cloud"):
                if name and notes:
                    save_to_cloud(name, notes, st.session_state.get("flashcards", []))
                    st.success("Saved to Firebase!")
                else:
                    st.warning("Enter name and notes.")

        if "flashcards" in st.session_state:
            st.subheader("🧠 Flashcards")
            st.caption("Rate each card before saving so the progress report can find your strong and weak areas.")

            mastery = st.session_state.setdefault("mastery", {})

            for index, card in enumerate(st.session_state["flashcards"]):
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
        docs = get_notes_for_user(user["login_id"])
        show_progress_report(docs)

    with tab_saved:
        docs = get_notes_for_user(user["login_id"])
        show_saved_sessions(docs)


def show_admin_app(user):
    st.sidebar.success(f"Logged in as {user['display_name']}")
    if st.sidebar.button("Logout"):
        logout_user()
        st.rerun()

    st.subheader("Admin Dashboard")

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

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Users", len(user_rows))
    col2.metric("Study Sessions", len(session_df))
    col3.metric("Flashcards", int(session_df["Flashcards"].sum()) if not session_df.empty else 0)
    col4.metric("Weak Cards", int(session_df["Weak"].sum()) if not session_df.empty else 0)

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

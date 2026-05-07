# App Store Publishing Guide

This project is a hosted Streamlit app. To publish it to Apple App Store or Google Play, use the Capacitor wrapper in `mobile/`.

## Public App URL

```text
https://ai-cloud-study-saver.onrender.com
```

## What This Wrapper Does

- Packages the public Render app inside a native iOS/Android shell.
- Keeps Firebase, Groq, and Streamlit secrets on Render.
- Adds native app identity: `com.aicloudstudysaver.app`.
- Provides a starter app icon at `mobile/assets/app-icon.svg`.

## Required Accounts

- Apple Developer Program account for iOS publishing.
- Google Play Console account for Android publishing.
- Render app must be deployed and working before review.
- A public privacy policy URL. A starter policy is included in `PRIVACY.md`.

## Build Setup

From the repository root:

```bash
cd mobile
npm install
npm run add:ios
npm run add:android
npm run sync
```

Open the native projects:

```bash
npm run ios
npm run android
```

## iOS App Store Steps

1. Open the iOS project from `npm run ios`.
2. In Xcode, set your Apple Team under Signing & Capabilities.
3. Confirm bundle identifier: `com.aicloudstudysaver.app`.
4. Set app version and build number.
5. Add app icons generated from `mobile/assets/app-icon.svg`.
6. Archive from Xcode.
7. Upload to App Store Connect.
8. Fill out app metadata, privacy answers, screenshots, and submit for review.

## Google Play Steps

1. Open Android Studio from `npm run android`.
2. Confirm package name: `com.aicloudstudysaver.app`.
3. Generate a signed release bundle.
4. Upload the `.aab` file to Google Play Console.
5. Fill out store listing, data safety, screenshots, content rating, and submit for review.

## Store Metadata Draft

App name:

```text
AI Cloud Study Saver
```

Short description:

```text
Turn notes into AI flashcards and track study progress.
```

Full description:

```text
AI Cloud Study Saver helps students turn class notes, PDF files, and pasted study material into focused AI flashcards. Students can rate each card as Strong, Review, or Weak, save study sessions in the cloud, and track progress over time. The admin view helps monitor saved sessions, flashcard volume, and common weak areas.
```

Keywords:

```text
study, flashcards, AI, notes, education, exam prep, revision
```

Category:

```text
Education
```

Privacy policy:

```text
Use a public URL for PRIVACY.md after GitHub publishes it, or host the policy on your own website.
```

## Review Notes

App reviewers need a working test account. Create a student account before submission or provide admin credentials through the private review notes field.

Do not include secrets, Firebase JSON, Groq API keys, or `.env` content in app store notes, screenshots, or repository files.

## Important Store Review Reality

Apple may reject apps that are only a thin webview without enough app-like value. This wrapper is a publishing foundation, but the app should feel polished on mobile, include stable login, clear privacy policy, useful saved sessions, and reliable AI generation before submission.

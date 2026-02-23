#!/usr/bin/env python3
"""
One-time local helper: runs the Google OAuth browser flow, then prints
the resulting token.json as a base64 string you can paste into your
cloud host's GOOGLE_TOKEN_B64 environment variable.

Usage:
    python execution/auth_setup.py

Prerequisites:
    - credentials.json in the project root (download from Google Cloud Console)
"""

import os
import sys
import base64
import pickle

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCOPES = ["https://www.googleapis.com/auth/calendar"]
CREDENTIALS_FILE = os.path.join(
    _ROOT, os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
)
TOKEN_FILE = os.path.join(_ROOT, "token.json")


def main():
    # ── Step 1: Run OAuth flow (or refresh existing token) ────────────
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token...")
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"ERROR: {CREDENTIALS_FILE} not found.")
                print("Download it from Google Cloud Console -> APIs & Services -> Credentials.")
                sys.exit(1)
            print("Opening browser for Google Calendar authorization...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
        print(f"Token saved to {TOKEN_FILE}")

    # ── Step 2: Encode token.json as base64 ──────────────────────────
    with open(TOKEN_FILE, "rb") as f:
        token_b64 = base64.b64encode(f.read()).decode("utf-8")

    print("\n" + "=" * 60)
    print("  GOOGLE_TOKEN_B64 (copy everything between the lines)")
    print("=" * 60)
    print(token_b64)
    print("=" * 60)
    print("\nPaste this value as the GOOGLE_TOKEN_B64 environment variable")
    print("in your Railway / Render / cloud dashboard.")


if __name__ == "__main__":
    main()

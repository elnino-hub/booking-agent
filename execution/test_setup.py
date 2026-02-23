import os
import sqlite3
import requests
import sys
from execution import history_manager

def test_sqlite():
    print("[1/3] Testing SQLite History...", end=" ")
    try:
        if os.path.exists("history.db"):
            os.remove("history.db")
        history_manager.save_message("test_user", "user", "Hello")
        hist = history_manager.get_recent_history("test_user")
        if len(hist) == 1 and hist[0]['content'] == "Hello":
            print("SUCCESS")
        else:
            print(f"FAILED (Unexpected count or content: {hist})")
    except Exception as e:
        print(f"FAILED ({e})")

def test_credentials():
    print("[2/3] Checking for Google Credentials...", end=" ")
    if os.path.exists("credentials.json"):
        print("FOUND (credentials.json exists)")
    else:
        print("MISSING (credentials.json not found in root)")

def test_api_import():
    print("[3/3] Testing API Import...", end=" ")
    try:
        from execution import api
        print("SUCCESS (Module imports without error)")
    except ImportError as e:
        print(f"FAILED (Import error: {e})")
    except Exception as e:
        print(f"FAILED ({e})")

if __name__ == "__main__":
    print("--- System Verification ---")
    test_sqlite()
    test_credentials()
    test_api_import()
    print("-------------------------")

#!/usr/bin/env python3
import os
import sys
import requests

TOKEN = sys.argv[1] if len(sys.argv) > 1 else os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")

if not TOKEN:
    print("Usage: python get_facebook_page_id.py <PAGE_ACCESS_TOKEN>")
    print("Or set FACEBOOK_PAGE_ACCESS_TOKEN env var")
    sys.exit(1)

url = "https://graph.facebook.com/v18.0/me/accounts"
params = {"access_token": TOKEN}

try:
    response = requests.get(url, params=params, timeout=10)
    data = response.json()

    if data.get("data"):
        print("Your Facebook Pages:")
        print("=" * 50)
        for page in data["data"]:
            print(f"Page Name: {page.get('name')}")
            print(f"Page ID: {page.get('id')}")
            print(f"Access Token: {page.get('access_token')}")
            print("-" * 30)
    else:
        print(f"Error: {data}")
except Exception as e:
    print(f"Error: {e}")

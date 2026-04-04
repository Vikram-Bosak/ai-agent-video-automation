#!/usr/bin/env python3
import os
import sys
import requests

TOKEN = sys.argv[1] if len(sys.argv) > 1 else os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")

if not TOKEN:
    print("Usage: python get_page_ids.py <PAGE_ACCESS_TOKEN>")
    print("\nOr set FACEBOOK_PAGE_ACCESS_TOKEN env var")
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
            print(f"Access Token: {page.get('access_token')[:50]}...")
            print("-" * 30)

            # Get Instagram Business Account
            page_id = page.get("id")
            ig_url = f"https://graph.facebook.com/v18.0/{page_id}"
            ig_params = {"fields": "instagram_business_account", "access_token": TOKEN}
            ig_response = requests.get(ig_url, params=ig_params, timeout=10)
            ig_data = ig_response.json()

            if ig_data.get("instagram_business_account"):
                print(
                    f"Instagram Business Account ID: {ig_data['instagram_business_account']['id']}"
                )
            print()
    else:
        print(f"Error: {data}")
except Exception as e:
    print(f"Error: {e}")

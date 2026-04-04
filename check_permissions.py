#!/usr/bin/env python3
"""
Script to check Facebook/Instagram permissions.
"""

import requests
import os

TOKEN = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")
PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")

if not TOKEN or not PAGE_ID:
    print("Please set FACEBOOK_PAGE_ACCESS_TOKEN and FACEBOOK_PAGE_ID in .env")
    exit(1)

# Check permissions
url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/permissions"
params = {"access_token": TOKEN}

response = requests.get(url, params=params)
print("Permissions:")
print(response.json())

# Check what the page can do
url2 = f"https://graph.facebook.com/v18.0/{PAGE_ID}"
params2 = {"fields": "name,access_token", "access_token": TOKEN}
response2 = requests.get(url2, params=params2)
print("\nPage info:")
print(response2.json())

#!/usr/bin/env python3
"""
GitHub Secrets Setup Script
============================
Fixes the PEM private key corruption issue in GitHub Secrets.

PROBLEM:
When you store a Google Service Account JSON file directly in GitHub Secrets,
the newline characters in the private_key field get stripped/corrupted.
This causes: "Unable to load PEM file. InvalidData(InvalidPadding)"

SOLUTION:
Base64-encode the entire JSON file and store THAT in GitHub Secrets.
The workflow decodes it back to a valid JSON file.

Usage:
    python setup_github_secrets.py path/to/service_account.json

This will output:
1. The base64-encoded string to copy into GitHub Secrets
2. The correct workflow YAML snippet to decode it
"""

import sys
import os
import json
import base64


def main():
    if len(sys.argv) < 2:
        print("Usage: python setup_github_secrets.py <path_to_service_account.json>")
        print("\nExample:")
        print("  python setup_github_secrets.py service_account.json")
        sys.exit(1)

    filepath = sys.argv[1]

    if not os.path.exists(filepath):
        print(f"ERROR: File not found: {filepath}")
        sys.exit(1)

    # Step 1: Validate the JSON file
    print("=" * 60)
    print("🔍 Step 1: Validating service account JSON...")
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ JSON is INVALID: {e}")
        print("   The file is already corrupted!")
        print("   Download a fresh copy from Google Cloud Console.")
        sys.exit(1)

    # Check required fields
    required = ["type", "project_id", "private_key_id", "private_key",
                "client_email", "client_id", "auth_uri", "token_uri"]
    missing = [k for k in required if k not in data]
    if missing:
        print(f"❌ Missing required fields: {missing}")
        sys.exit(1)

    # Check private key
    pk = data["private_key"]
    if "-----BEGIN" not in pk or "-----END" not in pk:
        print("❌ private_key field looks corrupted (no PEM markers)")
        sys.exit(1)

    if "\n" not in pk:
        print("⚠️  WARNING: private_key has no newlines! PEM keys MUST have newlines.")
        print("   Download a fresh copy from Google Cloud Console.")
        sys.exit(1)

    print(f"✅ Valid JSON with all required fields")
    print(f"   Project: {data.get('project_id', 'N/A')}")
    print(f"   Email: {data.get('client_email', 'N/A')}")
    print(f"   Key has {pk.count(chr(10))} newlines ✅")

    # Step 2: Base64 encode
    print(f"\n📦 Step 2: Base64 encoding...")
    with open(filepath, "rb") as f:
        raw_bytes = f.read()

    encoded = base64.b64encode(raw_bytes).decode("ascii")
    print(f"✅ Encoded: {len(encoded)} characters")

    # Step 3: Verify round-trip
    print(f"\n✅ Step 3: Verifying round-trip decode...")
    decoded = base64.b64decode(encoded).decode("utf-8")
    decoded_data = json.loads(decoded)
    assert decoded_data["private_key"] == data["private_key"], "Private key mismatch!"
    assert decoded_data["client_email"] == data["client_email"], "Client email mismatch!"
    print("✅ Round-trip verification PASSED!")

    # Step 4: Output instructions
    print(f"\n{'=' * 60}")
    print("📋 SETUP INSTRUCTIONS")
    print(f"{'=' * 60}")

    print(f"""
1️⃣  Go to your GitHub repo → Settings → Secrets and variables → Actions

2️⃣  Click "New repository secret"

3️⃣  Name: GOOGLE_SERVICE_ACCOUNT_JSON_B64

4️⃣  Value: Copy the base64 string below 👇

━━━ BASE64 STRING (copy everything below) ━━━
{encoded}
━━━ END BASE64 STRING ━━━

5️⃣  Also add these secrets if not already present:
    • GOOGLE_DRIVE_FOLDER_ID = {os.getenv('GOOGLE_DRIVE_FOLDER_ID', '<your-folder-id>')}

6️⃣  Update your GitHub Actions workflow to decode the secret.
   Add this step BEFORE running main.py:

```yaml
- name: Setup Service Account
  env:
    SA_JSON_B64: ${{ secrets.GOOGLE_SERVICE_ACCOUNT_JSON_B64 }}
  run: |
    echo "$SA_JSON_B64" | base64 -d > service_account.json
    echo "✅ Service account file created"
```

7️⃣  In your .env or workflow, set:
    GOOGLE_SERVICE_ACCOUNT_FILE=service_account.json

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Done! Your PEM key will now work correctly.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

    # Save base64 to file for easy copy
    output_file = "service_account_b64.txt"
    with open(output_file, "w") as f:
        f.write(encoded)
    print(f"💾 Base64 string also saved to: {output_file}")
    print(f"   You can cat this file and copy-paste into GitHub Secrets.")


if __name__ == "__main__":
    main()

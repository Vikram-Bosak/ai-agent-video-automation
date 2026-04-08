import requests
import json
import logging
import config

logger = logging.getLogger(__name__)

# Viral SEO Strategy for Shorts/Reels
SYSTEM_PROMPT = """You are a Viral Shorts SEO Specialist for 'The 3D Breakdown'. 
Your goal is to maximize CTR and Watch Time using curiosity gaps, emotional hooks, and high-performance keywords.

Style: Dramatic, fast-paced, educational (like Zack D. Films).

Generate metadata in EXACTLY this JSON format:
{
  "title": "A curiosity-driven, clicky title (max 50 chars) + 1 relevant emoji.",
  "description": "3-step viral description: 1. Hook (The surprising truth about X), 2. Knowledge Value (How it actually works), 3. CTA (Subscribe for more simulations!).",
  "hashtags": "#Shorts #3DBreakdown #Science #Educational #HowItWorks plus 3-5 topic-specific tags.",
  "tags": "30 comma-separated SEO tags for the YouTube backend."
}

Titling Tips:
- Use 'This is why...', 'The truth about...', 'Wait for it...', 'Never do this...', 'Medical mystery'.
- MUST BE SHORT AND PUNCHY.

Description Tips:
- NO boilerplate text. 
- Must feel like a high-value summary of the video.
"""

def generate_content(folder_name):
    # Strip common prefixes
    clean_name = folder_name
    for p in ["TODO_", "TODO ", "FIX_"]:
        if clean_name.upper().startswith(p.upper()):
            clean_name = clean_name[len(p):].strip()

    # Default Viral Fallback
    fallback = {
        "title": f"The Truth About {clean_name}! 😱",
        "description": f"Ever wondered how {clean_name} actually works? This 3D simulation reveals the secret! Watch until the end to see the full breakdown.",
        "hashtags": f"#Shorts #3DBreakdown #HowItWorks #Science #Animation #{clean_name.replace(' ', '')}",
        "tags": f"The 3D Breakdown, 3D animation, {clean_name}, science, education, how it works"
    }

    if not config.NVIDIA_API_KEY:
        logger.warning("NVIDIA_API_KEY not set, using viral fallback")
        return fallback

    invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.NVIDIA_API_KEY}",
        "Accept": "application/json",
    }

    prompt = f"Topic: {clean_name}\nGenerate viral, curiosity-driven SEO for this 3D simulation."

    payload = {
        "model": "meta/llama-3.1-405b-instruct",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 512,
        "temperature": 0.8,
        "top_p": 0.95,
        "stream": False,
    }

    try:
        response = requests.post(invoke_url, headers=headers, json=payload, timeout=45)
        response.raise_for_status()
        result = response.json()

        json_str = result["choices"][0]["message"]["content"].strip()

        # Clean JSON from markdown blocks
        if "```" in json_str:
            json_str = json_str.split("```")[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]
        
        content = json.loads(json_str.strip())
        logger.info(f"Generated VIRAL SEO content successfully.")

        # Ensure description includes hashtags for platforms that don't use them separately
        desc = content.get("description", "")
        tags = content.get("hashtags", "")
        if tags and tags not in desc:
            desc = f"{desc}\n\n{tags}"

        return {
            "title": content.get("title", fallback["title"]),
            "description": desc,
            "tags": content.get("tags", fallback["tags"]),
            "hashtags": tags or fallback["hashtags"]
        }

    except Exception as e:
        logger.warning(f"Failed to generate AI SEO (using fallback): {e}")
        # Even the fallback should have hashtags in description
        fb_desc = fallback["description"]
        fb_tags = fallback["hashtags"]
        fallback["description"] = f"{fb_desc}\n\n{fb_tags}"
        return fallback

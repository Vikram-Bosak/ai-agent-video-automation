import requests
import json
import logging
import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a YouTube SEO expert for a 3D animation educational Shorts channel
called "The 3D Breakdown". The channel explains science, anatomy, survival,
history, and bizarre real-world events using 3D CGI animation, X-Ray views,
and medical simulations. Style is similar to Zack D. Films.

Generate metadata in EXACTLY this JSON format, nothing else:
- title: Max 60 characters, curiosity hook, 1 emoji at end.
- description: 
  Line 1: Curiosity hook.
  Line 2: What viewer will learn.
  Line 3: CTA -> 'Subscribe to The 3D Breakdown for more!'
  Line 4: 3-5 hashtags (start with #Shorts #3DBreakdown + 2-3 topic-specific).
- tags: 30-35 comma-separated tags (specific topic tags first, then broad category tags). 
  Always include: The 3D Breakdown, 3D animation, 3D simulation, anatomy animation, x-ray view, educational shorts, how it works, Zack D Films style, science explained, CGI animation.

Focus on virality, curiosity, and high-quality educational SEO."""

def generate_content(folder_name):
    # Strip common prefixes if they exist to keep metadata clean
    clean_name = folder_name
    prefixes = ["TODO_", "TODO ", "FIX_"] # Add others if needed
    for p in prefixes:
        if clean_name.upper().startswith(p.upper()):
            clean_name = clean_name[len(p):].strip()

    if not config.NVIDIA_API_KEY:
        logger.warning("NVIDIA_API_KEY not set, using fallback content")
        return {
            "title": clean_name,
            "description": f"Check out this video about {clean_name}!",
            "tags": clean_name.lower().replace(" ", ","),
            "hashtags": f"#{clean_name.replace(' ', '')}",
        }

    invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.NVIDIA_API_KEY}",
        "Accept": "application/json"
    }

    prompt = f"Generate optimized metadata for a video about: {clean_name}. (Note: Ignore any technical prefixes like TODO if present)."
    
    payload = {
        "model": "meta/llama-3.1-405b-instruct",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1024,
        "temperature": 0.7,
        "top_p": 0.95,
        "stream": False,
    }

    try:
        response = requests.post(invoke_url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        json_str = result['choices'][0]['message']['content'].strip()
        
        if json_str.startswith("```json"):
            json_str = json_str[7:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]

        content = json.loads(json_str.strip())

        logger.info(f"Generated SEO content successfully using NVIDIA API.")
        
        return {
            "title": content.get("title", ""),
            "description": content.get("description", ""),
            "tags": content.get("tags", ""),
            "hashtags": content.get("hashtags", ""),
        }
    except Exception as e:
        logger.warning(f"Failed to parse JSON from NVIDIA API: {e}")

        return {
            "title": folder_name,
            "description": f"Check out this video about {folder_name}!",
            "tags": folder_name.lower().replace(" ", ","),
            "hashtags": f"#{folder_name.replace(' ', '')}",
        }

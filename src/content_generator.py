import requests
import json
import logging
import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a social media content optimization expert. Given a folder name that represents a video topic, generate optimized metadata for social media platforms.

Output a JSON object with exactly these fields:
- title: Catchy SEO-friendly title (max 100 chars)
- description: Engaging description with keywords (max 5000 chars)
- tags: Comma-separated relevant tags (max 500 chars)
- hashtags: Space-separated hashtags (max 500 chars)

Focus on virality, SEO, and trending topics."""

def generate_content(folder_name):
    if not config.NVIDIA_API_KEY:
        logger.warning("NVIDIA_API_KEY not set, using fallback content")
        return {
            "title": folder_name,
            "description": f"Check out this video about {folder_name}!",
            "tags": folder_name.lower().replace(" ", ","),
            "hashtags": f"#{folder_name.replace(' ', '')}",
        }

    invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.NVIDIA_API_KEY}",
        "Accept": "application/json"
    }

    prompt = f"Generate optimized metadata for a video about: {folder_name}"
    
    payload = {
        "model": "google/gemma-4-31b-it",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1024,
        "temperature": 0.7,
        "top_p": 0.95,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }

    try:
        response = requests.post(invoke_url, headers=headers, json=payload)
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

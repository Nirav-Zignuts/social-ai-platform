import requests
from pathlib import Path
from urllib.parse import quote

def generate_image(prompt: str, workspace_id: str, post_id: str) -> str | None:
    try:
        encoded_prompt = quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
        response = requests.get(url, timeout=60)
        response.raise_for_status()

        save_dir = Path(f"storage/generated_images/{workspace_id}")
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / f"{post_id}.jpeg"
        save_path.write_bytes(response.content)
        return str(save_path)
    except Exception as e:
        logger.error(f"Failed to generate or save image: {str(e)}")
        return None
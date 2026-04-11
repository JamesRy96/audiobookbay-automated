import re


def sanitize_title(title: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", title).strip()

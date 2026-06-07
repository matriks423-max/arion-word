import re
import unicodedata

_TYPE_PREFIX = {
    "character": "char",
    "hook": "hook",
    "technique": "tech",
    "world_doc": "world",
}


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def entity_id(entity_type: str, name: str) -> str:
    prefix = _TYPE_PREFIX[entity_type]
    return f"{prefix}-{slugify(name)}"

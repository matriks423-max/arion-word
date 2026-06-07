from __future__ import annotations

import json

from engine.llm.base import ChatClient

_EPISODE_SCHEMA = {"type": "object"}  # writer returns a free-form episode dict (validated downstream)

WRITER_SYSTEM = (
    "You are the lead writer for Arion World, a 16+ epic anime fantasy. Equivalent exchange "
    "governs all power; no character or outcome is protected. Write a full episode as JSON: "
    "{title, logline, summary, cliffhanger, scenes:[{scene_number, location, prose, dialogue}], "
    "patch_ops:[canon mutation ops]}. patch_ops use: create_entity, set_field, append_to_list, "
    "add_relationship, mark_hook_revealed, record_death. Stay consistent with the provided canon."
)

EDITOR_SYSTEM = (
    "You are the editor for Arion World. Polish prose quality and internal consistency without "
    "changing plot facts. Return the same JSON episode structure, improved."
)


class Writer:
    def __init__(self, chat: ChatClient):
        self.chat = chat

    def write(self, episode_number: int, canon_context: str) -> dict:
        user = (f"Write Episode {episode_number}.\n\nRELEVANT CANON:\n{canon_context}\n\n"
                "Return the episode JSON described in the system prompt.")
        return self.chat.complete_json(WRITER_SYSTEM, user, schema=_EPISODE_SCHEMA, max_tokens=16000)

    def revise(self, episode_number: int, canon_context: str, draft: dict, issues: list[dict]) -> dict:
        user = (f"Revise Episode {episode_number}. The continuity critic flagged these issues — "
                f"fix ALL of them:\n{json.dumps(issues, ensure_ascii=False)}\n\n"
                f"RELEVANT CANON:\n{canon_context}\n\n"
                f"CURRENT DRAFT:\n{json.dumps(draft, ensure_ascii=False)[:120000]}")
        return self.chat.complete_json(WRITER_SYSTEM, user, schema=_EPISODE_SCHEMA, max_tokens=16000)


class Editor:
    def __init__(self, chat: ChatClient):
        self.chat = chat

    def polish(self, episode: dict, canon_context: str) -> dict:
        user = (f"RELEVANT CANON:\n{canon_context}\n\nEPISODE TO POLISH:\n"
                f"{json.dumps(episode, ensure_ascii=False)[:120000]}")
        return self.chat.complete_json(EDITOR_SYSTEM, user, schema=_EPISODE_SCHEMA, max_tokens=16000)

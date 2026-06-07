from __future__ import annotations

import os
from pathlib import Path

import yaml

from engine.llm.anthropic_client import AnthropicChat
from engine.llm.nvidia_client import NvidiaChat, NvidiaEmbeddings


def load_config(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def build_chat(stage_cfg: dict):
    provider = stage_cfg["provider"]
    if provider == "anthropic":
        return AnthropicChat(model=stage_cfg["model"])
    if provider == "nvidia":
        return NvidiaChat(api_key=os.environ["NVIDIA_API_KEY"], model=stage_cfg["model"])
    raise ValueError(f"unknown provider: {provider}")


def build_critic_voters(critic_cfg: dict) -> list:
    key = os.environ["NVIDIA_API_KEY"]
    return [NvidiaChat(api_key=key, model=m) for m in critic_cfg["voters"]]


def build_embeddings(emb_cfg: dict) -> NvidiaEmbeddings:
    return NvidiaEmbeddings(api_key=os.environ["NVIDIA_API_KEY"], model=emb_cfg["model"])

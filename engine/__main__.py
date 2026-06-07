from __future__ import annotations

import argparse
import sys
from pathlib import Path

from engine.canon.store import CanonStore, ValidationFailed
from engine.canon.index import build_index
from engine.migrate import migrate_all

DEFAULT_CANON = Path(__file__).parent.parent / "canon"


def cmd_validate(args) -> int:
    store = CanonStore(Path(args.canon))
    failures = 0
    for eid in store.list_ids():
        try:
            store.validate(store.load(eid))
        except ValidationFailed as exc:
            print(f"INVALID {eid}: {exc}", file=sys.stderr)
            failures += 1
    if failures:
        print(f"{failures} invalid ent/ies", file=sys.stderr)
        return 1
    print(f"OK -- {len(store.list_ids())} entities valid")
    return 0


def cmd_index(args) -> int:
    store = CanonStore(Path(args.canon))
    index = build_index(store)
    print(f"index built: {index['count']} entities -> {store.root / '_index.json'}")
    return 0


def cmd_migrate(args) -> int:
    store = CanonStore(Path(args.canon))
    report = migrate_all(Path(args.src), store)
    for k, v in report.items():
        print(f"{k}: {len(v)}")
    build_index(store)
    return 0


def cmd_episode(args) -> int:
    import json as _json
    from engine.llm.config import (load_config, build_chat, build_critic_voters, build_embeddings)
    from engine.retrieval_embed import EmbeddingRetriever
    from engine.critic import Critic
    from engine.writer import Writer, Editor
    from engine.pipelines.episode import EpisodePipeline

    store = CanonStore(Path(args.canon))
    cfg = load_config(Path(args.models))
    retriever = EmbeddingRetriever(store, build_embeddings(cfg["embeddings"]))
    if args.reindex:
        retriever.build()
    pipe = EpisodePipeline(
        store=store,
        writer=Writer(build_chat(cfg["writer"])),
        critic=Critic(build_critic_voters(cfg["critic"])),
        editor=Editor(build_chat(cfg["editor"])),
        retriever=retriever,
    )
    state = store.root / "_state.json"
    number = _json.loads(state.read_text())["next_episode"] if state.exists() else 1
    result = pipe.run(episode_number=number)
    print(_json.dumps(result, indent=2))
    return 0 if result["status"] == "committed" else 2


def main(argv=None) -> int:
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--canon", default=str(DEFAULT_CANON))

    parser = argparse.ArgumentParser(prog="engine")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", parents=[parent])
    sub.add_parser("index", parents=[parent])
    m = sub.add_parser("migrate", parents=[parent])
    m.add_argument("--src", default="story_bible")
    ep = sub.add_parser("episode", parents=[parent])
    ep.add_argument("--models", default="models.yaml")
    ep.add_argument("--reindex", action="store_true")

    args = parser.parse_args(argv)
    return {
        "validate": cmd_validate, "index": cmd_index,
        "migrate": cmd_migrate, "episode": cmd_episode,
    }[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())

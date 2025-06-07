import argparse
import json
from pathlib import Path
from . import storage, ratings, gemini_util


def _placeholder_handler(name):
    def handler(args):
        print(f"{name} command is in development.")

    return handler


def _cmd_tree(args):
    index_path = Path(args.index)
    data = json.loads(index_path.read_text())
    print(data.get("title", "Hr\u00f6nir Encyclopedia"))
    for pos, fname in sorted(data.get("chapters", {}).items(), key=lambda x: int(x[0])):
        print(f"{pos}: {fname}")


def _cmd_validate(args):
    chapter = Path(args.chapter)
    if not chapter.exists() or not chapter.is_file():
        print("chapter file not found")
        return
    if "book" not in chapter.parts:
        print("chapter must reside in the book/ directory")
        return
    print("chapter looks valid")


def _cmd_store(args):
    chapter = Path(args.chapter)
    prev_uuid = args.prev
    uuid_str = storage.store_chapter(chapter, prev_uuid)
    print(uuid_str)


def _cmd_vote(args):
    ratings.record_vote(args.position, args.voter, args.winner, args.loser)
    print("vote recorded")


def _cmd_audit(args):
    book_dir = Path("book")
    for chapter in book_dir.glob("**/*.md"):
        storage.validate_or_move(chapter)

    fork_dir = Path("forking_path")
    if fork_dir.exists():
        for csv in fork_dir.glob("*.csv"):
            storage.audit_forking_csv(csv)


def _cmd_auto_vote(args):
    gemini_util.auto_vote(args.position, args.prev, args.voter)
    print("auto vote recorded")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Hr\u00f6nir Encyclopedia CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    synth = subparsers.add_parser("synthesize", help="in development")
    synth.set_defaults(func=_placeholder_handler("synthesize"))

    validate = subparsers.add_parser("validate", help="validate a chapter file")
    validate.add_argument("chapter", help="path to chapter markdown file")
    validate.set_defaults(func=_cmd_validate)

    submit = subparsers.add_parser("submit", help="in development")
    submit.set_defaults(func=_placeholder_handler("submit"))

    tree = subparsers.add_parser("tree", help="print the chapter tree")
    tree.add_argument("--index", default="book/book_index.json", help="index file")
    tree.set_defaults(func=_cmd_tree)

    ranking = subparsers.add_parser("ranking", help="in development")
    ranking.set_defaults(func=_placeholder_handler("ranking"))

    vote = subparsers.add_parser("vote", help="record a duel result")
    vote.add_argument("--position", type=int, required=True, help="chapter position")
    vote.add_argument("--voter", required=True, help="uuid of forking path casting the vote")
    vote.add_argument("--winner", required=True, help="winning chapter id")
    vote.add_argument("--loser", required=True, help="losing chapter id")
    vote.set_defaults(func=_cmd_vote)

    export = subparsers.add_parser("export", help="in development")
    export.set_defaults(func=_placeholder_handler("export"))

    store = subparsers.add_parser("store", help="store chapter by UUID")
    store.add_argument("chapter", help="path to chapter markdown file")
    store.add_argument("--prev", help="uuid of previous chapter")
    store.set_defaults(func=_cmd_store)

    audit = subparsers.add_parser("audit", help="validate and repair storage")
    audit.set_defaults(func=_cmd_audit)

    autovote = subparsers.add_parser("autovote", help="generate chapters with Gemini and vote")
    autovote.add_argument("--position", type=int, required=True, help="chapter position")
    autovote.add_argument("--prev", required=True, help="uuid of previous chapter")
    autovote.add_argument("--voter", required=True, help="uuid of forking path casting the vote")
    autovote.set_defaults(func=_cmd_auto_vote)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()


import argparse
import json
import subprocess
from pathlib import Path
from . import storage, ratings, gemini_util

# ~~~~~ The Labyrinth CLI ~~~~~


def _phantom_command(sigil):
    """Return a placeholder handler for yet unwritten actions."""

    def wander(_):
        print(f"'{sigil}' wanders unwritten through the library.")

    return wander


def _cmd_labyrinth_map(args):
    scroll_path = Path(args.index)
    compendium = json.loads(scroll_path.read_text())
    print(compendium.get("title", "Hr\u00f6nir Encyclopedia"))
    for position, scroll in sorted(compendium.get("chapters", {}).items(), key=lambda x: int(x[0])):
        print(f"{position}: {scroll}")


def _cmd_inspect_scroll(args):
    scroll_path = Path(args.chapter)
    if not scroll_path.exists() or not scroll_path.is_file():
        print("scroll file not found")
        return
    if "book" not in scroll_path.parts:
        print("scroll must reside in the book/ directory")
        return
    print("scroll looks valid")


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


def _git_remove_deleted():
    """Stage deleted files in git if available."""
    try:
        output = subprocess.check_output(["git", "ls-files", "--deleted"], text=True)
    except Exception:
        return
    for path in output.splitlines():
        if path:
            subprocess.run(["git", "rm", "-r", "--ignore-unmatch", path])


def _cmd_clean(args):
    storage.purge_fake_hronirs()
    fork_dir = Path("forking_path")
    if fork_dir.exists():
        for csv in fork_dir.glob("*.csv"):
            storage.purge_fake_forking_csv(csv)
    rating_dir = Path("ratings")
    if rating_dir.exists():
        for csv in rating_dir.glob("*.csv"):
            storage.purge_fake_votes_csv(csv)
    if getattr(args, "git", False):
        _git_remove_deleted()
    print("cleanup complete")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Hr\u00f6nir Encyclopedia CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    synth = subparsers.add_parser("synthesize", help="in development")
    synth.set_defaults(func=_phantom_command("synthesize"))

    validate = subparsers.add_parser("validate", help="validate a chapter file")
    validate.add_argument("chapter", help="path to chapter markdown file")
    validate.set_defaults(func=_cmd_inspect_scroll)

    submit = subparsers.add_parser("submit", help="in development")
    submit.set_defaults(func=_phantom_command("submit"))

    tree = subparsers.add_parser("tree", help="print the chapter tree")
    tree.add_argument("--index", default="book/book_index.json", help="index file")
    tree.set_defaults(func=_cmd_labyrinth_map)

    ranking = subparsers.add_parser("ranking", help="in development")
    ranking.set_defaults(func=_phantom_command("ranking"))

    vote = subparsers.add_parser("vote", help="record a duel result")
    vote.add_argument("--position", type=int, required=True, help="chapter position")
    vote.add_argument("--voter", required=True, help="uuid of forking path casting the vote")
    vote.add_argument("--winner", required=True, help="winning chapter id")
    vote.add_argument("--loser", required=True, help="losing chapter id")
    vote.set_defaults(func=_cmd_vote)

    export = subparsers.add_parser("export", help="in development")
    export.set_defaults(func=_phantom_command("export"))

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

    clean = subparsers.add_parser("clean", help="remove invalid entries")
    clean.add_argument(
        "--git",
        action="store_true",
        help="also remove deleted files from the git index",
    )
    clean.set_defaults(func=_cmd_clean)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()


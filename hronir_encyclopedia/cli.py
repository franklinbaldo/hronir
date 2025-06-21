import argparse
import json
import subprocess
from pathlib import Path

from . import database, gemini_util, ratings, storage


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
    print("chapter looks valid")


def _cmd_store(args):
    chapter = Path(args.chapter)
    prev_uuid = args.prev
    uuid_str = storage.store_chapter(chapter, prev_uuid)
    print(uuid_str)


def _cmd_vote(args):
    with database.open_database() as conn:
        ratings.record_vote(args.position, args.voter, args.winner, args.loser, conn=conn)
    print("vote recorded")


def _cmd_audit(args):
    book_dir = Path("book")
    for chapter in book_dir.glob("**/*.md"):
        storage.validate_or_move(chapter)

    fork_dir = Path("forking_path")
    if fork_dir.exists():
        for csv in fork_dir.glob("*.csv"):
            storage.audit_forking_csv(csv)


def _cmd_synthesize(args):
    # A lógica de 'auto_vote' é, na verdade, a síntese de dois ramos
    # e o registro de uma "opinião" inicial sobre eles.
    # Poderíamos renomear auto_vote para synthesize_and_vote
    print(
        f"Synthesizing two new hrönirs from predecessor '{args.prev}' at position {args.position}..."
    )
    with database.open_database() as conn:
        # O 'voter' aqui é o próprio agente gerador, identificado por um UUID fixo ou dinâmico
        voter_uuid = "00000000-agent-0000-0000-000000000000"  # Exemplo de UUID do agente
        winner_uuid = gemini_util.auto_vote(args.position, args.prev, voter_uuid, conn=conn)
    print(f"Synthesis complete. New canonical candidate: {winner_uuid}")


def _cmd_ranking(args):
    ranking_data = ratings.get_ranking(args.position)
    if ranking_data.empty:
        print(f"No ranking data found for position {args.position}.")
    else:
        print(f"Ranking for Position {args.position}:")
        print(ranking_data.to_string(index=False))


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

    synth = subparsers.add_parser(
        "synthesize", help="Generate competing chapters from a predecessor"
    )
    synth.add_argument("--position", type=int, required=True, help="Chapter position")
    synth.add_argument("--prev", required=True, help="UUID of the previous chapter")
    synth.set_defaults(func=_cmd_synthesize)

    validate = subparsers.add_parser("validate", help="validate a chapter file")
    validate.add_argument("chapter", help="path to chapter markdown file")
    validate.set_defaults(func=_cmd_validate)

    submit = subparsers.add_parser("submit", help="in development")
    submit.set_defaults(func=_placeholder_handler("submit"))

    tree = subparsers.add_parser("tree", help="print the chapter tree")
    tree.add_argument("--index", default="book/book_index.json", help="index file")
    tree.set_defaults(func=_cmd_tree)

    ranking = subparsers.add_parser("ranking", help="Show Elo rankings for a chapter position")
    ranking.add_argument(
        "--position", type=int, required=True, help="The chapter position to rank."
    )
    ranking.set_defaults(func=_cmd_ranking)

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

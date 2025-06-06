import argparse
import csv
import json
from pathlib import Path


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


def _cmd_vote(args):
    ratings_dir = Path("ratings")
    ratings_dir.mkdir(exist_ok=True)
    rating_file = ratings_dir / f"position_{args.position:03d}.csv"

    hronirs_path = Path("hronirs/index.txt")
    hronirs_path.parent.mkdir(exist_ok=True)
    if hronirs_path.exists():
        known_hronirs = set(hronirs_path.read_text().splitlines())
    else:
        known_hronirs = set()

    for h in args.hronirs:
        if h not in known_hronirs:
            known_hronirs.add(h)
    hronirs_path.write_text("\n".join(sorted(known_hronirs)) + "\n")

    entries = []
    if rating_file.exists():
        with rating_file.open() as fh:
            for row in csv.reader(fh):
                entries.append([row[0], int(row[1])])

    for path, _ in entries:
        if path == args.path:
            print("path already exists; vote rejected")
            return

    entries.append([args.path, 1])
    entries.sort(key=lambda x: (-x[1], x[0]))

    def _distance(p, top, rank):
        return abs(len(p.split("->")) - len(top.split("->"))) + rank

    top_path = entries[0][0]
    distances = []
    for idx, (p, c) in enumerate(entries, start=1):
        distances.append(_distance(p, top_path, idx))

    max_distance = max(distances)
    new_idx = next(i for i, (p, _) in enumerate(entries) if p == args.path)

    if distances[new_idx] == max_distance:
        entries[new_idx][1] = 0
        result = "vote recorded but too distant to count"
    else:
        result = "vote counted"

    with rating_file.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerows(entries)

    print(result)


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

    export = subparsers.add_parser("export", help="in development")
    export.set_defaults(func=_placeholder_handler("export"))

    vote = subparsers.add_parser("vote", help="submit a vote with proof of work")
    vote.add_argument("--position", type=int, required=True, help="chapter position")
    vote.add_argument("--path", required=True, help="unique forking path")
    vote.add_argument("--hronirs", nargs=2, required=True, help="two discovered hronirs")
    vote.set_defaults(func=_cmd_vote)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()


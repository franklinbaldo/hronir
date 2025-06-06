import argparse
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

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()


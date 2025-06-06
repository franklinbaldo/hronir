import argparse
import json
from pathlib import Path

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

    export = subparsers.add_parser("export", help="in development")
    export.set_defaults(func=_phantom_command("export"))

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()


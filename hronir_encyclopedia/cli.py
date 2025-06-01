import argparse
import os
import json

def update_book_index(position, variant_id, title, path):
    book_index_path = "book/book_index.json"
    try:
        with open(book_index_path, "r") as f:
            index_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: {book_index_path} not found. Initializing new index.")
        index_data = {"title": "The Hrönir Encyclopedia", "chapters": {}}

    if position not in index_data["chapters"]:
        # This part creates a generic title for the *position* if it's new.
        # The actual chapter *variant* title is passed in the `title` argument.
        index_data["chapters"][position] = {
            "title": f"Chapter {position} - Placeholder Title", # Generic title for the position
            "variants": {}
        }

    # Add the new variant's specific title and path
    index_data["chapters"][position]["variants"][variant_id] = {
        "title": title, # This is the specific title like "Chapter 01a"
        "path": path
    }

    with open(book_index_path, "w") as f:
        json.dump(index_data, f, indent=2)
    print(f"Updated {book_index_path} with new chapter {position}_{variant_id}.")

def main():
    parser = argparse.ArgumentParser(description="CLI for the Hrönir Encyclopedia.")
    subparsers = parser.add_subparsers(title="commands", dest="command")

    # Placeholder for the 'continue' command
    continue_parser = subparsers.add_parser("continue", help="Generate initial branches from the seed chapter.")

    args = parser.parse_args()

    if args.command == "continue":
        print("Placeholder: This command will generate initial branches.")

        next_position = "01"
        variant_id = "a"

        chapter_dir = os.path.join("book", next_position)
        os.makedirs(chapter_dir, exist_ok=True)

        file_path = os.path.join(chapter_dir, f"{next_position}_{variant_id}.md")
        file_title = f"Chapter {next_position}{variant_id}"

        with open(file_path, "w") as f:
            f.write(f"# {file_title}\n")
        print(f"Created new chapter file: {file_path}")

        # This will be updated later to use the actual new chapter details
        update_book_index(position=next_position, variant_id=variant_id, title=file_title, path=file_path)

    elif args.command is None:
        parser.print_help()

if __name__ == "__main__":
    main()

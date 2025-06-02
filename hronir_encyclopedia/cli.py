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
        print("Processing 'continue' command...") # Changed placeholder

        book_index_path = "book/book_index.json"
        try:
            with open(book_index_path, "r") as f:
                index_data = json.load(f)
        except FileNotFoundError:
            print(f"Error: {book_index_path} not found. Please ensure the encyclopedia is initialized (e.g., with a seed chapter).")
            return

        # Determine the next chapter position
        numeric_keys = [k for k in index_data.get("chapters", {}).keys() if k.isdigit()]
        if not numeric_keys:
            # This implies not even "00" (seed chapter) is present or correctly formatted.
            # For 'continue' to work, we expect "00" to be there.
            # If truly empty, starting at "01" might be desired for a first chapter *after* a potential "00".
            # However, if "00" is the base, the next should be "01".
            # Let's assume "00" should exist. If no numeric keys, implies something is wrong or it's the very first run.
            print("Warning: No numeric chapter keys found in book_index.json. Defaulting to create chapter '01'.")
            current_max_pos_num = 0 # Results in next_chapter_number = 1
        else:
            current_max_pos_num = max(int(k) for k in numeric_keys)

        next_chapter_number = current_max_pos_num + 1
        next_position = f"{next_chapter_number:02d}"
        variant_id = "a" # 'continue' always creates the 'a' variant of the next chapter

        print(f"Determined next chapter position: {next_position}, variant: {variant_id}")

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

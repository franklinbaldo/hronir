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

    # Parser for the 'synthesize' command
    synthesize_parser = subparsers.add_parser("synthesize", help="Synthesize a new chapter variant for a given position.")
    synthesize_parser.add_argument("--position", type=str, required=True, help="The chapter position (e.g., '00', '01').")
    synthesize_parser.add_argument("--variant_id", type=str, required=False, default=None, help="The specific variant ID to create (e.g., 'a', 'b', 'custom_id').")
    synthesize_parser.add_argument(
        "--variants",
        type=int,
        required=False,
        default=None,
        help="Number of new variants to auto-generate (uses next available letters a-z)."
    )

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

    elif args.command == "synthesize":
        position = args.position
        variant_id = args.variant_id
        num_to_generate = args.variants

        if variant_id is None and num_to_generate is None:
            # This could also be handled by a custom action or by checking after parse_args if specific combinations are met.
            # For now, a runtime check is fine.
            # synthesize_parser.error("Either --variant_id or --variants must be specified.") # This exits the program
            print("Error: For 'synthesize', either --variant_id or --variants must be specified.")
            return

        if variant_id is not None and num_to_generate is not None:
            # synthesize_parser.error("Specify either --variant_id or --variants, not both.") # This exits the program
            print("Error: For 'synthesize', specify either --variant_id or --variants, not both.")
            return

        book_index_path = "book/book_index.json"
        try:
            with open(book_index_path, "r") as f:
                index_data = json.load(f)
        except FileNotFoundError:
            print(f"Error: {book_index_path} not found. Please ensure the encyclopedia is initialized.")
            return

        if position not in index_data.get("chapters", {}):
            print(f"Error: Position {position} not found in {book_index_path}. Use 'continue' to create new chapter positions or ensure the position exists.")
            return

        existing_variants_at_pos = index_data["chapters"][position].get("variants", {})

        if variant_id is not None: # Logic for --variant_id
            print(f"Processing 'synthesize' for specific variant: position {position}, variant_id {variant_id}...")
            if variant_id in existing_variants_at_pos:
                print(f"Error: Variant {variant_id} already exists for position {position} in {book_index_path}.")
                return

            chapter_dir = os.path.join("book", position)
            os.makedirs(chapter_dir, exist_ok=True)
            file_path = os.path.join(chapter_dir, f"{position}_{variant_id}.md")
            file_title = f"Chapter {position}{variant_id}"
            with open(file_path, "w") as f:
                f.write(f"# {file_title}\n")
            print(f"Created new chapter file: {file_path}")
            update_book_index(position, variant_id, file_title, file_path)

        elif num_to_generate is not None: # Logic for --variants n
            print(f"Processing 'synthesize' to generate {num_to_generate} variants for position {position}...")

            last_char_code = ord('a') - 1
            for vid in existing_variants_at_pos.keys():
                if len(vid) == 1 and 'a' <= vid <= 'z':
                    last_char_code = max(last_char_code, ord(vid))

            generated_this_run = 0
            # Need to re-load index_data or pass existing_variants_at_pos to update_book_index
            # if it's to be kept perfectly in sync for a single run of multiple generations.
            # For now, update_book_index writes to file, so a simpler loop:

            # This loop assumes that update_book_index correctly updates the main file,
            # and for this run, we just need to find the next available slot based on the initial scan.
            # A more robust way for multi-generation in one call would be to update 'existing_variants_at_pos'
            # in memory after each successful generation within this loop.

            temp_existing_variants = set(existing_variants_at_pos.keys())

            for _ in range(num_to_generate):
                next_variant_char_found = False
                current_attempt_char_code = last_char_code + 1

                while current_attempt_char_code <= ord('z'):
                    new_variant_id_char = chr(current_attempt_char_code)
                    if new_variant_id_char not in temp_existing_variants:
                        # Available
                        chapter_dir = os.path.join("book", position)
                        os.makedirs(chapter_dir, exist_ok=True)

                        new_file_path = os.path.join(chapter_dir, f"{position}_{new_variant_id_char}.md")
                        new_file_title = f"Chapter {position}{new_variant_id_char}"
                        with open(new_file_path, "w") as f:
                            f.write(f"# {new_file_title}\n")
                        print(f"Created new chapter file: {new_file_path}")
                        update_book_index(position, new_variant_id_char, new_file_title, new_file_path)

                        temp_existing_variants.add(new_variant_id_char) # Mark as used for this run
                        last_char_code = current_attempt_char_code # Update for next iteration search
                        generated_this_run += 1
                        next_variant_char_found = True
                        break
                    current_attempt_char_code += 1 # Try next char

                if not next_variant_char_found:
                    print(f"Warning: Could not find an available single-letter variant ('a'-'z') for position {position}. Stopped after generating {generated_this_run} variants.")
                    break

            if generated_this_run > 0:
                print(f"Successfully generated {generated_this_run} new variants for position {position}.")
            elif num_to_generate > 0:
                print(f"Could not generate any new variants for position {position} (perhaps all letters 'a'-'z' are taken or another issue).")

    elif args.command is None:
        parser.print_help()

if __name__ == "__main__":
    main()

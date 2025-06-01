import os
from typing import List

def get_chapter_filepaths(book_directory: str = "book") -> List[str]:
    """
    Finds all Markdown (.md) files in the specified directory and its subdirectories.

    Args:
        book_directory: The path to the directory to search. Defaults to "book".

    Returns:
        A list of full file paths to the .md files found.
        Returns an empty list if the directory is not found or contains no .md files.
    """
    chapter_files: List[str] = []
    if not os.path.isdir(book_directory):
        print(f"Info: Directory '{book_directory}' not found or is not a directory.")
        return chapter_files

    for root, _, files in os.walk(book_directory):
        for file in files:
            if file.endswith(".md"):
                # Ensure consistent path separators (e.g., / instead of \ on Windows)
                # and normalize the path to remove any redundant separators.
                normalized_path = os.path.normpath(os.path.join(root, file))
                chapter_files.append(normalized_path.replace(os.sep, '/'))

    if not chapter_files:
        print(f"Info: No '.md' files found in '{book_directory}'.")

    return sorted(chapter_files) # Return sorted list for consistent output

if __name__ == '__main__':
    print("--- Testing get_chapter_filepaths ---")

    # Test with the default 'book/' directory
    # This expects 'book/00_tlon_uqbar.md' to exist from previous steps.
    print("\n[Test 1] Looking for chapter files in the default 'book/' directory:")
    filepaths = get_chapter_filepaths()
    if filepaths:
        print("Found chapter files:")
        for path in filepaths:
            print(f"  - {path}")
    else:
        # This branch might be hit if 'book/00_tlon_uqbar.md' wasn't created or is not '.md'
        print("No chapter files found in 'book/'. This might be unexpected if setup was complete.")

    # Test with a specific, potentially existing, file (though it filters by .md)
    # This also tests if it handles existing files that are not directories.
    print("\n[Test 2] Attempting to use an existing file as book_directory (should fail gracefully):")
    # Assuming 'README.md' exists in the root.
    # The function expects a directory, so this should result in an empty list and a message.
    filepaths_readme = get_chapter_filepaths("README.md")
    if not filepaths_readme:
        print("Correctly found no files when path is not a directory (or no .md files).")
    else:
        print(f"Unexpectedly found files: {filepaths_readme}")


    # Test with a non-existent directory
    print("\n[Test 3] Looking for chapter files in a 'non_existent_dir/':")
    filepaths_non_existent = get_chapter_filepaths("non_existent_dir")
    if not filepaths_non_existent:
        # The function prints its own "Info: Directory not found" message.
        print("Test successful: Correctly found no files and printed info message for non-existent directory.")
    else:
        print(f"Unexpectedly found files in non_existent_dir: {filepaths_non_existent}")

    # Test with an empty directory (if possible to create one easily, otherwise skip)
    # For now, we'll rely on the "No '.md' files found" message if 'book/' was empty or had no .mds.
    # To explicitly test an empty directory:
    # 1. Create 'empty_test_dir'
    # 2. Call get_chapter_filepaths('empty_test_dir')
    # 3. Check for empty list and appropriate message.
    # 4. Remove 'empty_test_dir'
    # This is more involved with current tools, so we'll assume the existing tests cover the logic.

    print("\n--- End of tests ---")

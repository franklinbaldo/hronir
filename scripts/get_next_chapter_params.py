import sys
from pathlib import Path

# Add parent directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

try:
    from hronir_encyclopedia import canon_new, storage
except ImportError:
    print("Error: Could not import 'hronir_encyclopedia'. Ensure PYTHONPATH is set.")
    sys.exit(1)


def main():
    dm = storage.DataManager()
    if not dm._initialized:
        dm.initialize_and_load()

    canonical_chain = canon_new.calculate_canonical_path(dm)

    if canonical_chain:
        tip = canonical_chain[-1]
        next_pos = tip["position"] + 1
        prev_hrönir_uuid = tip["hrönir_uuid"]
        print(f"Canonical path tip found at Position {tip['position']}.")
    else:
        # Start at 0
        next_pos = 0
        prev_hrönir_uuid = ""
        print("No canonical path found. Starting at Position 0.")

    print(f"Next position: {next_pos}")
    print(f"Predecessor UUID: {prev_hrönir_uuid}")

    # Save to files for GitHub Actions
    Path(".next_pos").write_text(str(next_pos))
    Path(".prev_uuid").write_text(str(prev_hrönir_uuid))


if __name__ == "__main__":
    main()

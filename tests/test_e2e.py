import subprocess
import sys


def test_main_script_output():
    """
    Tests that running main.py produces the expected output.
    """
    # Run the main.py script as a subprocess
    process = subprocess.run(
        [sys.executable, "main.py"],
        capture_output=True,
        text=True,
        cwd=".",  # Run from the project root to ensure main.py is found
        check=True,  # Raise an exception for non-zero exit codes
    )

    # Assert that the standard output is as expected
    assert process.stdout == "Hello from app!\n"
    assert process.stderr == ""

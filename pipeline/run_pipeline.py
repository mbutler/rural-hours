"""
Run the full Rural Hours ESN data pipeline in order:
1. Schema setup
2. NLP extraction (from rural_hours.md)
3. Taxonomic harmonization (GBIF name backbone)
4. GBIF occurrence retrieval
5. Static data export
"""
import subprocess
import sys
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent
ROOT = PIPELINE_DIR.parent


def run_script(name: str, *args: str) -> bool:
    """Run a Python script from the pipeline directory."""
    venv_python = ROOT / "venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        venv_python = ROOT / "venv" / "bin" / "python"
    cmd = [str(venv_python), str(PIPELINE_DIR / name), *args]
    result = subprocess.run(cmd, cwd=str(ROOT))
    return result.returncode == 0


def main() -> None:
    print("=== Rural Hours ESN Pipeline ===\n")
    steps = [
        ("schema.py", "Schema"),
        ("extract.py", "NLP extraction"),
        ("harmonize.py", "Taxonomic harmonization"),
        ("occurrences.py", "GBIF occurrences"),
        ("export_data.py", "Static export"),
    ]
    for script, label in steps:
        print(f"--- {label} ---")
        if not run_script(script):
            print(f"Pipeline failed at {script}")
            sys.exit(1)
    print("\n=== Pipeline complete ===")


if __name__ == "__main__":
    main()

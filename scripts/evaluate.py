"""Run from the repository root: python scripts/evaluate.py"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.evaluation import evaluate


if __name__ == "__main__":
    print(json.dumps(evaluate("sample.csv", "sample_truth.json"), indent=2))

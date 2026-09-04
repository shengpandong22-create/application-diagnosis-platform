import argparse
from pathlib import Path

from app_diagnosis.evaluation.failure_review import load_case_review


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a Markdown review for a failed eval case.")
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    review = load_case_review(args.result_dir, case_id=args.case_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(review, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()

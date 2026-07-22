"""
Administrative cleanup utility.

Default mode is DRY RUN to prevent accidental destructive operations.
Use --execute to actually delete users.
"""

import argparse
import traceback
from pathlib import Path

from dotenv import load_dotenv

from app.domain import models
from app.infrastructure.database import SessionLocal
from app.interfaces.admin_router import delete_user


def run_cleanup(execute: bool, output_file: str) -> int:
    root = Path(__file__).resolve().parent
    load_dotenv(dotenv_path=root / ".env")

    db = SessionLocal()
    try:
        users = (
            db.query(models.User)
            .filter(models.User.role != models.RoleEnum.ADMIN)
            .all()
        )

        with open(output_file, "w", encoding="utf-8") as f:
            mode = "EXECUTE" if execute else "DRY_RUN"
            f.write(f"Mode: {mode}\n")
            f.write(f"Found {len(users)} non-admin users.\n")
            for u in users:
                f.write(f"Candidate user: {u.id} - {u.email} - {u.role}\n")
                if not execute:
                    f.write("Skipped (dry-run).\n")
                    continue
                try:
                    res = delete_user(str(u.id), db=db)
                    f.write(f"Success: {res}\n")
                except Exception as exc:
                    f.write(f"Exception: {str(exc)}\n")
                    f.write(traceback.format_exc() + "\n")
                    db.rollback()
        return 0
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete non-admin users safely.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform deletions (default is dry-run).",
    )
    parser.add_argument(
        "--output",
        default="test_out.log",
        help="Output log path (default: test_out.log).",
    )
    args = parser.parse_args()
    return run_cleanup(execute=args.execute, output_file=args.output)


if __name__ == "__main__":
    raise SystemExit(main())

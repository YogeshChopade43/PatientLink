"""
One-time backfill script for patient ownership.

Usage example:
  python api/scripts/backfill_patient_owners.py --username admin --dry-run
  python api/scripts/backfill_patient_owners.py --username admin

By default, this assigns only unowned patients (owner_user_id is NULL/empty)
to the selected user account.
"""
import argparse
import os
from pathlib import Path

from sqlalchemy import create_engine, text


def _default_patient_db_url() -> str:
    return os.environ.get("DATABASE_URL", "sqlite:///./api/patientlink.db")


def _default_auth_db_url() -> str:
    # Optional dedicated auth DB URL; fallback to Django sqlite DB for local setup.
    if os.environ.get("AUTH_DATABASE_URL"):
        return os.environ["AUTH_DATABASE_URL"]

    auth_db = Path(__file__).resolve().parents[2] / "auth_service" / "db.sqlite3"
    return f"sqlite:///{auth_db.as_posix()}"


def _engine(db_url: str):
    connect_args = {"check_same_thread": False} if "sqlite" in db_url else {}
    return create_engine(db_url, connect_args=connect_args)


def _user_id_for_username(auth_engine, username: str):
    with auth_engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM users WHERE username = :username"),
            {"username": username},
        ).fetchone()
        return str(row[0]) if row else None


def main():
    parser = argparse.ArgumentParser(description="Backfill Patient.owner_user_id")
    parser.add_argument("--username", required=True, help="Target account username")
    parser.add_argument("--patient-db-url", default=_default_patient_db_url())
    parser.add_argument("--auth-db-url", default=_default_auth_db_url())
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite owner_user_id for all patients, not just unowned",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show affected row count without applying changes",
    )
    args = parser.parse_args()

    auth_engine = _engine(args.auth_db_url)
    patient_engine = _engine(args.patient_db_url)

    user_id = _user_id_for_username(auth_engine, args.username)
    if not user_id:
        raise SystemExit(f"User '{args.username}' not found in auth DB.")

    where_clause = "1=1" if args.overwrite else "(owner_user_id IS NULL OR owner_user_id = '')"

    with patient_engine.begin() as conn:
        count = conn.execute(
            text(f"SELECT COUNT(*) FROM patients WHERE {where_clause}")
        ).scalar_one()

        print(f"Target username: {args.username}")
        print(f"Resolved user_id: {user_id}")
        print(f"Patients to update: {count}")

        if args.dry_run:
            print("Dry run only. No rows updated.")
            return

        conn.execute(
            text(f"UPDATE patients SET owner_user_id = :user_id WHERE {where_clause}"),
            {"user_id": user_id},
        )
        print("Backfill complete.")


if __name__ == "__main__":
    main()

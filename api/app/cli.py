"""Command-line account tools, for when nobody can sign in yet.

    python -m app.cli create-user --email you@example.com --name "Your Name" [--role admin]

Prompts for the password (or reads one line from stdin). Where there's no
terminal, e.g. a one-off ECS task, --generate-password makes a random one and
prints it once: change it after signing in. Run it where the API runs, with
the same DATABASE_URL (see docs/auth.md for docker-compose and ECS).
"""

import argparse
import getpass
import secrets
import sys

from sqlalchemy import select

from .database import SessionLocal, init_db
from .models import User, UserRole
from .security import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH, hash_password


def create_user(email: str, name: str, role: UserRole, password: str) -> User:
    init_db()
    with SessionLocal() as db:
        email = email.strip().lower()
        if db.scalar(select(User).where(User.email == email)):
            raise SystemExit(f"An account for {email} already exists")
        user = User(email=email, name=name, role=role, password_hash=hash_password(password))
        db.add(user)
        db.commit()
        return user


def _read_password() -> str:
    if not sys.stdin.isatty():  # e.g. piped in
        return sys.stdin.readline().rstrip("\n")
    password = getpass.getpass("Password: ")
    if getpass.getpass("Repeat password: ") != password:
        raise SystemExit("Passwords don't match")
    return password


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-user", help="Create an account (an admin, by default)")
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--role", choices=[r.value for r in UserRole], default=UserRole.ADMIN.value)
    create.add_argument(
        "--generate-password", action="store_true", help="Make a random password and print it once"
    )
    args = parser.parse_args(argv)

    password = secrets.token_urlsafe(18) if args.generate_password else _read_password()
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise SystemExit(f"Passwords must be {MIN_PASSWORD_LENGTH} to {MAX_PASSWORD_LENGTH} characters")
    user = create_user(args.email, args.name, UserRole(args.role), password)
    print(f"Created {user.role.value} {user.email}. They set up an authenticator at their first sign-in.")
    if args.generate_password:
        print(f"Temporary password: {password}  (change it on the Account page after signing in)")


if __name__ == "__main__":
    main()

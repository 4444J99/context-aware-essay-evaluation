"""Loopback workbench and protected metadata service commands."""
import argparse
import os
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="edu essay evaluation services")
    parser.add_argument("command", choices=["serve", "serve-backend", "migrate"])
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.command == "migrate":
        from .database import migrate
        migrate(os.environ["EDU_MIGRATION_DATABASE_URL"])
        print("Applied edu schema migration")
        return
    if args.command == "serve-backend":
        uvicorn.run("essay_evaluation.backend:configured_backend", factory=True,
                    host="127.0.0.1", port=args.port, access_log=False)
        return
    # Never bind this unauthenticated synthetic workbench to a public interface.
    uvicorn.run("essay_evaluation.api:create_app", factory=True,
                host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()

"""Local-only synthetic workbench."""
import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="edu synthetic essay intake")
    parser.add_argument("command", choices=["serve"])
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    # Never bind this unauthenticated synthetic workbench to a public interface.
    uvicorn.run("essay_evaluation.api:create_app", factory=True,
                host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()

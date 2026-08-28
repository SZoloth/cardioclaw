"""Compatibility entrypoint for the Oracle V4 cron command."""

from cardioclaw.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["generate", "--type", "weekly"]))

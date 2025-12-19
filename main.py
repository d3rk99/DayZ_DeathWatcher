from __future__ import annotations

import argparse
import json
import asyncio
from pathlib import Path

from src.bot.deathwatcher import start_bot
from src.models.config import load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the DeathWatcher Discord bot")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.json"),
        help="Path to configuration JSON file",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_config = json.loads(Path(args.config).read_text())
    config = load_config(raw_config)
    asyncio.run(start_bot(config))


if __name__ == "__main__":
    main()

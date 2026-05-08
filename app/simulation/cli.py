from __future__ import annotations

import argparse
import asyncio
import json

from dotenv import load_dotenv

from app.config.loader import load_settings
from app.simulation.runner import run_simulation
from app.utils.logger import configure_logging


async def async_main(config_path: str) -> None:
    load_dotenv()
    settings = load_settings(config_path)
    configure_logging(settings.app.log_level)
    summary = await run_simulation(settings)
    print(json.dumps(summary, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/local_test.yaml")
    args = parser.parse_args()
    asyncio.run(async_main(args.config))


if __name__ == "__main__":
    main()

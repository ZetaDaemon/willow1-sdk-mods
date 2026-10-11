import fnmatch
import sys
from pathlib import Path
from typing import Protocol

import unrealsdk
from unrealsdk import logging

from mods_base import command
from set_command_enhancements.command_utils import autoregister

cookedpc_dir = Path(sys.executable).parent.parent / "WillowGame" / "CookedPC"
all_upks: list[Path] = []

for root, _dirs, files in cookedpc_dir.walk():
    for file in files:
        filepath = root / file
        if filepath.suffix != ".upk":
            continue
        all_upks.append(filepath.relative_to(cookedpc_dir).with_suffix(""))


class LoadPackageArgs(Protocol):
    """Protocol to represent the args for load_package."""

    package: str
    list: bool


@autoregister
@command()  # pyright: ignore[reportArgumentType]
def load_package(args: LoadPackageArgs) -> None:
    upks = fnmatch.filter(all_upks, args.package)  # pyright: ignore[reportArgumentType]

    if args.list:
        if upks == all_upks:
            logging.info("All known packages:")
        else:
            logging.info(f"Packages matching '{args.package}':")
        logging.info("=" * 80)
        for package in upks:
            logging.info(package)
        return

    if len(upks) <= 0:
        logging.info(f"Could not find package '{args.package}'!")
    elif len(upks) > 10:  # noqa: PLR2004
        logging.info(f"'{args.package}' matches more than 10 packages!")
    else:
        for package in upks:
            unrealsdk.load_package(str(package))


load_package.add_argument("package", nargs="?", default="*")
load_package.add_argument(
    "--list",
    action="store_true",
    help="List all packages matching the given pattern, instead of trying to load any.",
)

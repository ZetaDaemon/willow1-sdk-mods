import argparse
import re
import shlex
import traceback

import unrealsdk
from mods_base import command

from set_command_enhancements.command_utils import autoregister

RE_OPTIONAL_ARG = re.compile(r"^\s*--?\w+")

cached_lines: list[str] = []


def pyb_splitter(args: str) -> list[str]:
    if RE_OPTIONAL_ARG.match(args):
        return shlex.split(args)
    return [args[1:]]


def run_pyb(args: argparse.Namespace, cached_lines: list[str]) -> None:
    if args.print:
        for line in cached_lines:
            unrealsdk.logging.info(line)
    if args.exec:
        joined = "\n".join(cached_lines)
        try:
            exec(joined)  # noqa: S102
        except Exception:  # noqa: BLE001
            unrealsdk.logging.error("Error occurred during 'pyb' command:")
            unrealsdk.logging.error(joined)
            if len(cached_lines) > 1:
                unrealsdk.logging.error("=" * 80)

            traceback.print_exc()
    if args.discard or args.exec:
        cached_lines.clear()

    if args.exec or args.discard or args.print:
        return

    cached_lines.append(args.args[0])


@autoregister
@command(cmd="py|", splitter=pyb_splitter)
def pyb(args: argparse.Namespace) -> None:
    run_pyb(args, cached_lines)


pyb.add_argument("args", nargs=argparse.REMAINDER)
pyb.add_argument("-x", "--exec", action="store_true", help="Executes stored lines.")
pyb.add_argument("-d", "--discard", action="store_true", help="Discards stored lines.")
pyb.add_argument("-p", "--print", action="store_true", help="Prints stored lines.")

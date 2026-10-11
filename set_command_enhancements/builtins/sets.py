from __future__ import annotations

import argparse
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Protocol

import unrealsdk

from mods_base import command, hook
from set_command_enhancements.command_utils import (
    CommandFlags,
    CommandFlagsAction,
    autoregister,
    parse_object,
    set_command_splitter,
    split_property_path,
    walk_to_property,
)

if TYPE_CHECKING:
    from common.Engine import GameInfo  # pyright: ignore[reportMissingModuleSource]


class SetArgs(Protocol):
    """Protocol to represent the args for set_special."""

    object: str
    property_path: str
    value: list[str]
    level: str | None
    flags: CommandFlags


ANY_LEVEL = "Any_Level"
HOTFIXES: dict[str, list[SetArgs]] = defaultdict(list)


def do_set(object_path: str, property_path: str, value: str, flags: CommandFlags) -> None:
    obj = parse_object(object_path)
    if obj is None:
        if CommandFlags.Silent not in flags:
            unrealsdk.logging.error(f"Unable to find object {object_path}")
        return
    path = split_property_path(property_path)
    try:
        walk_to_property(obj, path, value, flags)
    except Exception as e:  # noqa: BLE001
        unrealsdk.logging.error(e)
        unrealsdk.logging.error(object_path, property_path, value)


@hook("Engine.GameInfo:PostCommitMapChange")
def post_load(game_info: GameInfo, *_: Any) -> None:
    if (level_name := game_info.WorldInfo.GetMapName()) == "FakeEntry":
        return
    for args in HOTFIXES[level_name] + HOTFIXES[ANY_LEVEL]:
        do_set(args.object, args.property_path, "".join(args.value), args.flags)


@autoregister
@command(splitter=set_command_splitter)  # pyright: ignore[reportArgumentType]
def sets(args: SetArgs) -> None:
    if args.level is not None:
        HOTFIXES[args.level].append(args)
        return
    do_set(args.object, args.property_path, "".join(args.value), args.flags)


sets.add_argument("object")
sets.add_argument("property_path")
sets.add_argument("value", nargs=argparse.REMAINDER)
sets.add_argument("-l", "--level", nargs="?", default=None)
sets.add_argument("-s", "--silent", action=CommandFlagsAction, flag_value=CommandFlags.Silent)
append_group = sets.parser.add_mutually_exclusive_group()
append_group.add_argument(
    "-a", "--append", action=CommandFlagsAction, flag_value=CommandFlags.Append
)
append_group.add_argument(
    "-e", "--extend", action=CommandFlagsAction, flag_value=CommandFlags.Extend
)

from __future__ import annotations

from typing import Protocol

import unrealsdk
from mods_base import command

from set_command_enhancements.ce_replacements.clone import parse_clone_target
from set_command_enhancements.command_utils import obj_name_splitter


class ConstructArgs(Protocol):
    """Protocol to represent the args for clone."""

    klass: str
    target: str


@command(splitter=obj_name_splitter)  # pyright: ignore[reportArgumentType]
def construct(args: ConstructArgs) -> None:
    kls = unrealsdk.find_class(args.klass)
    outer, name = parse_clone_target(args.target, kls.Name)
    if name is None:
        return
    try:
        unrealsdk.construct_object(kls, outer, name, 0x400004000)
    except Exception:  # noqa: BLE001
        return


construct.add_argument("klass")
construct.add_argument("target")

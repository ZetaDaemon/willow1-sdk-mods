import argparse
from dataclasses import dataclass
from typing import Protocol

import unrealsdk

from mods_base import command
from set_command_enhancements.command_utils import (
    CommandFlags,
    CommandFlagsAction,
    autoregister,
    set_command_splitter,
)

from .sets import HOTFIXES, do_set


class SetTemplateArgs(Protocol):
    """Protocol to represent the args for set_template."""

    object: str
    template: str
    level: str | None
    flags: CommandFlags


class SetTemplateCreateArgs(Protocol):
    """Protocol to represent the args for set_template_create."""

    template: str
    property_path: str
    value: list[str]


@dataclass
class SetArgsStruct:
    """Dataclass to represent the args for set_special."""

    object: str
    property_path: str
    value: list[str]
    level: str | None
    flags: CommandFlags


TEMPLATES: dict[str, tuple[str, list[str]]] = {}


@autoregister
@command()  # pyright: ignore[reportArgumentType]
def set_template(args: SetTemplateArgs) -> None:
    if (template := TEMPLATES.get(args.template)) is None:
        unrealsdk.logging.error(f"Template {args.template} not found")
        return
    path, value = template
    if args.level is not None:
        HOTFIXES[args.level].append(SetArgsStruct(args.object, path, value, args.level, args.flags))
        return
    do_set(args.object, path, "".join(value), args.flags)


set_template.add_argument("object")
set_template.add_argument("template")
set_template.add_argument("-l", "--level", nargs="?", default=None)
set_template.add_argument(
    "-s", "--silent", action=CommandFlagsAction, flag_value=CommandFlags.Silent
)
append_group = set_template.parser.add_mutually_exclusive_group()
append_group.add_argument(
    "-a", "--append", action=CommandFlagsAction, flag_value=CommandFlags.Append
)
append_group.add_argument(
    "-e", "--extend", action=CommandFlagsAction, flag_value=CommandFlags.Extend
)


@autoregister
@command(splitter=set_command_splitter)  # pyright: ignore[reportArgumentType]
def set_template_create(args: SetTemplateCreateArgs) -> None:
    TEMPLATES[args.template] = (args.property_path, args.value)


set_template_create.add_argument("template")
set_template_create.add_argument("property_path")
set_template_create.add_argument("value", nargs=argparse.REMAINDER)

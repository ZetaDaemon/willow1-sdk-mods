from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Protocol

import unrealsdk

from mods_base import command
from set_command_enhancements.command_utils import RE_OBJ_NAME, obj_name_splitter, parse_object

if TYPE_CHECKING:
    from unrealsdk.unreal import UObject

suppress_exists_warning: bool = False


def parse_clone_target(name: str, src_class: str) -> tuple[UObject | None, str] | tuple[None, None]:
    """Parse a full object name intended to be a clone target into it's outer object and name.

    If it's unable to parse or find the object, logs an error to console and returns None.

    Args:
        name: The full object name to parse.
        src_class: The class of the source object. The target must use this class (or object).

    Returns:
        A tuple of the target's outer object and it's name, or a tuple of two `None`s on error.

    """
    dst_match = RE_OBJ_NAME.match(name)
    if dst_match is None:
        unrealsdk.logging.error(f"Unable to parse object name {name}")
        return None, None

    dst_class = dst_match.group("class") or "Object"
    if dst_class not in ("Object", src_class):
        unrealsdk.logging.error(f"Cannot clone object of class {src_class} as class {dst_class}")
        return None, None

    with suppress(ValueError):
        dst_obj = unrealsdk.find_object(dst_class, dst_match.group("fullname"))
        if not suppress_exists_warning:
            unrealsdk.logging.error(f"Object '{dst_obj.PathName(dst_obj)}' already exists")
        return None, None

    dst_outer = dst_match.group("outer")
    dst_outer_object = None
    if dst_outer:
        try:
            dst_outer_object = unrealsdk.find_object("Object", dst_outer)
        except ValueError:
            unrealsdk.logging.error(f"Unable to find outer object {dst_outer}")
            return None, None

    return dst_outer_object, dst_match.group("name")


class CloneArgs(Protocol):
    """Protocol to represent the args for clone."""

    base: str
    clone: str


@command(splitter=obj_name_splitter)  # pyright: ignore[reportArgumentType]
def clone(args: CloneArgs) -> None:
    base = parse_object(args.base)
    if base is None:
        return
    outer, name = parse_clone_target(args.clone, base.Class.Name)
    if name is None:
        return
    try:
        cloned = unrealsdk.construct_object(base.Class, outer, name, 0x400004000, base)
    except Exception:  # noqa: BLE001
        return

    cloned.ObjectArchetype = base.ObjectArchetype


clone.add_argument("base")
clone.add_argument("clone")


class SuppressExistsArgs(Protocol):
    """Protocol to represent the args for suppress_exists."""

    new_state: bool


@command()  # pyright: ignore[reportArgumentType]
def suppress_exists(args: SuppressExistsArgs) -> None:
    global suppress_exists_warning
    suppress_exists_warning = args.new_state


suppress_exists.add_argument("new_state", type=bool)

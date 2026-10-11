from typing import Protocol

from mods_base import command
from set_command_enhancements.command_utils import obj_name_splitter, parse_object


class UnlockPackageArgs(Protocol):
    """Protocol to represent the args for unlock_package."""

    object: str
    undo: bool


@command(splitter=obj_name_splitter)  # pyright: ignore[reportArgumentType]
def unlock_package(args: UnlockPackageArgs) -> None:
    obj = parse_object(args.object)
    if obj is None:
        return

    if args.undo:
        obj.ObjectFlags &= ~4
    else:
        obj.ObjectFlags |= 4


unlock_package.add_argument("object", help="The object to unlock.")
unlock_package.add_argument(
    "-u", "--undo", action="store_true", help="Undo a previous unlock package call."
)

from typing import Protocol

from mods_base import command
from set_command_enhancements.command_utils import autoregister, parse_object


class KeepAliveArgs(Protocol):
    """Protocol to represent the args for keep_alive."""

    object: str
    undo: bool


@autoregister
@command()  # pyright: ignore[reportArgumentType]
def keep_alive(args: KeepAliveArgs) -> None:
    obj = parse_object(args.object)
    if obj is None:
        return

    if args.undo:
        obj.ObjectFlags &= ~0x4000
    else:
        obj.ObjectFlags |= 0x4000


keep_alive.add_argument("object", help="The object to keep alive.")
keep_alive.add_argument(
    "-u", "--undo", action="store_true", help="Undo a previous keep alive call."
)

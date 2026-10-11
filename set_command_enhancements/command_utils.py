from __future__ import annotations

import json
import re
import shlex
from argparse import Action, ArgumentParser, Namespace
from dataclasses import dataclass
from enum import IntFlag, auto
from importlib.util import find_spec
from typing import TYPE_CHECKING, Any, TypeGuard, cast, overload, override

import unrealsdk
from unrealsdk import unreal
from unrealsdk.unreal import (
    UClass,
    UEnum,
    UObject,
    UScriptStruct,
    WrappedArray,
    WrappedStruct,
    ZArrayProperty,
    ZProperty,
)

from mods_base import AbstractCommand

if TYPE_CHECKING:
    from collections.abc import Sequence

    from unrealsdk.unreal._uenum import (  # pyright: ignore[reportMissingModuleSource]
        _GenericUnrealEnum,  # pyright: ignore[reportPrivateUsage]
    )

# if command_extensions exists, import autoregister from that,
# otherwise, create a dummy function to just return the command.
# needed so commnads can still be autoregistered
if find_spec("command_extensions"):
    from command_extensions import (  # pyright: ignore[reportMissingImports]
        autoregister as autoregister,  # pyright: ignore[reportUnknownVariableType]  # noqa: PLC0414
    )
else:

    def autoregister[C: AbstractCommand](obj: C) -> C:
        return obj


class CommandFlags(IntFlag):
    """Int flags for command flag options."""

    NONE = 0
    Append = auto()
    Extend = auto()
    Silent = auto()


class CommandFlagsAction(Action):
    """Action to handle CommandFlags flag arguments.

    nargs is always 0.
    default is always CommandFlags.NONE.
    """

    flag_value: CommandFlags

    def __init__(  # noqa: D107
        self,
        flag_value: CommandFlags,
        option_strings: Sequence[str],
        dest: str = "flags",
        help: str | None = None,  # noqa: A002
    ) -> None:
        super().__init__(
            option_strings=option_strings, dest=dest, nargs=0, default=CommandFlags.NONE, help=help
        )
        self.flag_value = flag_value

    @override
    def __call__(
        self,
        parser: ArgumentParser,
        namespace: Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        current_value = getattr(namespace, self.dest, self.default)
        setattr(namespace, self.dest, current_value | self.flag_value)


def set_command_splitter(value: str) -> list[str]:
    lexer = shlex.shlex(value, posix=False)
    lexer.whitespace_split = True
    return list(lexer)


def obj_name_splitter(args: str) -> list[str]:
    """Custom argument splitter that returns object names as single tokens.

    Note that this makes the splitting less versatile - quoting is completely gone for example.

    Args:
        args: A string of arguments

    Returns:
        A list of individual arguments split out from the input string.

    """  # noqa: D401
    lex = shlex.shlex(args)
    lex.wordchars += ".:?+!,'\"\\-"
    lex.quotes = ""
    lex.whitespace_split = True
    return list(lex)


RE_OBJ_NAME = re.compile(
    r"^((?P<class>[\w?+!,'\"\\\-]+?)')?(?P<fullname>((?P<outer>[\w.:?+!,'\"\\\-]+)[.:])?(?P<name>[\w?+!,'\"\\\-]+))(?(class)'|)$",
    flags=re.IGNORECASE,
)


def parse_object(name: str) -> UObject | None:
    match = RE_OBJ_NAME.match(name)
    if match is None:
        return None

    class_ = match.group("class") or "Object"
    fullname = match.group("fullname")
    try:
        return unrealsdk.find_object(class_, fullname)
    except ValueError:
        return None


@dataclass
class ListType[T]:  # noqa: D101
    inner: T


type PrimitiveValue = str | float
type JSONDict = dict[str, "JSONValue"]
type JSONList = list["JSONValue"]
type JSONValue = PrimitiveValue | JSONDict | JSONList | None
type UValue = (
    str | int | float | bool | _GenericUnrealEnum | UObject | WrappedStruct | list["UValue"]
)

type PrimitiveType = type[PrimitiveValue]
type UNotListType = PrimitiveType | UEnum | UClass | UScriptStruct
type UListType = ListType["UType"]
type UType = UNotListType | UListType


def is_primitive(t: UType) -> TypeGuard[PrimitiveType]:
    return t in (str, int, float, bool)


def utype_to_type(prop: ZProperty) -> UType | None:  # noqa: C901
    match prop:
        case unreal.ZStrProperty() | unreal.ZNameProperty():
            t = str
        case unreal.ZFloatProperty():
            t = float
        case unreal.ZIntProperty():
            t = int
        case unreal.ZBoolProperty():
            t = bool
        case unreal.ZByteProperty(Enum=None):
            t = int
        case unreal.ZByteProperty() | unreal.ZEnumProperty():
            t = prop.Enum
        case unreal.ZObjectProperty():
            t = prop.PropertyClass
        case unreal.ZArrayProperty():
            if (inner_type := utype_to_type(prop.Inner)) is None:
                return None
            t = ListType(inner_type)
        case unreal.ZStructProperty():
            t = prop.Struct
        case _:
            unrealsdk.logging.error(f"Unable to handle property {prop}")
            return None
    # Fixed length arrays use ArrayDim and are not an ZArrayProperty
    if t is not None and prop.ArrayDim > 1:
        return ListType(t)
    return t


def list_to_array(value: JSONList, inner_type: UType) -> list[UValue]:
    return [convert_value(v, inner_type) for v in value]


def dict_to_struct(data: JSONDict, struct_type: UScriptStruct) -> WrappedStruct:
    new_struct = unrealsdk.make_struct(struct_type.Name)
    for k, v in data.items():
        field = struct_type._find_prop(k)
        t = utype_to_type(field)
        if t is None:
            continue
        val = convert_value(v, t)
        setattr(new_struct, k, val)
    return new_struct


def convert_to_enum(value: JSONValue, t: UEnum) -> int | None:
    if isinstance(value, int):
        return value
    py_enum = t._as_py()
    if isinstance(value, str):
        return py_enum[value]
    unrealsdk.logging.error(f"Cannot convert {value} to {t}")
    return None


def convert_to_object(value: JSONValue, t: UClass) -> UObject | None:
    if not isinstance(value, str):
        unrealsdk.logging.error("Value must be the object path as a string.")
        return None
    if value == "None":
        return None
    return unrealsdk.find_object(t, value)


def convert_to_struct(value: JSONValue, t: UScriptStruct) -> WrappedStruct | None:
    if not isinstance(value, dict):
        unrealsdk.logging.error("Struct values must be a dict.")
        return None
    return dict_to_struct(value, t)


@overload
def convert_value(value: JSONValue, t: UClass) -> UObject: ...
@overload
def convert_value(value: str, t: UEnum) -> int: ...
@overload
def convert_value(value: JSONValue, t: UListType) -> list[UValue]: ...
@overload
def convert_value(value: JSONValue, t: UNotListType) -> UValue: ...
def convert_value(value: JSONValue, t: UType | UClass) -> UValue | list[UValue] | None:  # noqa: PLR0911
    if is_primitive(t):
        if not isinstance(value, str | float | int | bool):
            unrealsdk.logging.error(f"Cannot convert {value} to {t}")
            return None
        return t(value)

    if isinstance(t, UEnum):
        return convert_to_enum(value, t)

    if isinstance(t, UClass):
        return convert_to_object(value, t)

    if isinstance(t, UScriptStruct):
        return convert_to_struct(value, t)

    if isinstance(t, ListType):
        if not isinstance(value, list):
            unrealsdk.logging.error(f"Value {value} is not a list")
            return None
        return list_to_array(value, t.inner)

    unrealsdk.logging.error(f"Unable to handle type {t} and value {value}")
    return None


PROPERTY_PATH_REGEX = r"((?<!\[)[a-zA-Z_]+|(?<=\[)\d+(?=\]))"


def split_property_path(property_path: str) -> list[str | int]:
    path = re.findall(PROPERTY_PATH_REGEX, property_path)
    return [int(x) if x.isdigit() else x for x in path]


def set_array_index(destination: WrappedArray, target: int, value: JSONValue) -> None:
    inner_type = utype_to_type(destination._type)
    if inner_type is None:
        msg = "Found None inner type of Array"
        raise TypeError(msg)
    uvalue = convert_value(value, inner_type)
    destination[target] = uvalue


def append_to_property(
    destination: UObject | WrappedStruct,
    target_prop: ZProperty,
    value: JSONValue,
    flags: CommandFlags,
) -> None:
    """Append to or extend an array."""
    if not isinstance(target_prop, ZArrayProperty):
        unrealsdk.logging.error(f"Cannot append to {target_prop} as it is not an array property.")
        return
    t = utype_to_type(target_prop.Inner)

    if t is None:
        msg = "Found None inner type of Array"
        raise TypeError(msg)

    current = destination._get_field(target_prop)
    if CommandFlags.Append in flags:
        current.append(convert_value(value, t))
    elif CommandFlags.Extend in flags:
        # Extend seems to not properly add the new items, it only increases length
        # So for now just append each item
        for item in convert_value(value, ListType(t)):
            current.append(item)


def set_property(
    destination: UObject | WrappedStruct | WrappedArray,
    target: str | int,
    value_str: str,
    flags: CommandFlags,
) -> None:
    value = cast("JSONValue", json.loads(value_str.replace("\\", "\\\\")))
    if isinstance(destination, WrappedArray):
        if not isinstance(target, int):
            unrealsdk.logging.error(f"{target} is not an index")
            return
        set_array_index(destination, target, value)
        return

    if isinstance(target, int):
        unrealsdk.logging.error("Cannot get an index from a non array property")
        return

    if isinstance(destination, UObject):
        target_prop = destination.Class._find_prop(target)
    else:
        target_prop = destination._type._find_prop(target)

    if flags & (CommandFlags.Append | CommandFlags.Extend):
        append_to_property(destination, target_prop, value, flags)
        return

    target_type = utype_to_type(target_prop)
    if target_type is None:
        msg = "Found None target type."
        raise ValueError(msg)
    value = convert_value(value, target_type)
    destination._set_field(target_prop, value)


def walk_to_property(
    destination: UObject | WrappedStruct | WrappedArray,
    path: list[str | int],
    value_str: str,
    flags: CommandFlags,
) -> None:
    """Walk the path to find the target property."""
    target = path.pop(0)
    if len(path) == 0:
        set_property(destination, target, value_str, flags)
        return
    if isinstance(destination, WrappedArray):
        if not isinstance(target, int):
            unrealsdk.logging.error(f"{target} is not an integer")
            return
        walk_to_property(destination[target], path, value_str, flags)
        return
    if not isinstance(target, str):
        unrealsdk.logging.error("Cannot index a struct or object.")
        return
    walk_to_property(getattr(destination, target), path, value_str, flags)

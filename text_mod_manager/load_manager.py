import contextlib
import ctypes
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path
from typing import Any

import unrealsdk
from unrealsdk.hooks import Block
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct

from mods_base import SETTINGS_DIR, CoopSupport, hook, register_mod
from ui_utils import TrainingBox

from .text_mod import FileTextMod, FolderTextMod, TextMod

TEXT_MOD_SETTINGS_DIR = SETTINGS_DIR / "text_mod_settings"
TEXT_MODS_DIR = Path(__file__).parent.parent.parent / "text_mods"
ALL_TEXT_MODS: list[TextMod] = []

LOADING_MSG = "Running all text mods, this will take a moment."
TRAINING_BOX_TEXT_VAR = "dialogue.htmlText"
notify_loading_msg = TrainingBox(
    title="Loading Mod",
    message=LOADING_MSG,
    on_input=lambda *_: Block,  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]
)


def find_mods() -> None:
    for p in TEXT_MODS_DIR.iterdir():
        tm = new_text_mod(p)
        if tm is None:
            continue
        ALL_TEXT_MODS.append(tm)
        register_mod(tm)


def new_text_mod(path: Path) -> TextMod | None:
    if path.is_file():
        if path.suffix != ".blmod":
            return None
        cls = FileTextMod
    elif path.is_dir():
        cls = FolderTextMod
    else:
        raise ValueError

    metadata = cls.extract_metadata(path)
    name = metadata.get("title", path.stem)
    author = metadata.get("author", cls.author)
    description = metadata.get("description", cls.description)
    version = metadata.get("version", cls.version)
    try:
        coop_support = CoopSupport[metadata.get("coop-support", "Unknown")]
    except KeyError:
        unrealsdk.logging.error(f"Invalid coop-support value in {path.name}")
        coop_support = cls.coop_support

    settings_file = TEXT_MOD_SETTINGS_DIR / f"{path.name}.json"
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.touch(exist_ok=True)

    return cls(
        name,
        author,
        description,
        version,
        coop_support=coop_support,
        settings_file=settings_file,
        mod_path=path,
    )


def exec_all_mods() -> None:
    for mod in ALL_TEXT_MODS:
        if mod.is_enabled:
            mod.exec_mod()


exec_iterator: Iterator[None]

frontend_func: BoundFunction
frontend_args: WrappedStruct


def set_bool(obj: UObject, offset: int, value: bool) -> None:
    ctypes.memset(obj._get_address() + offset, 1 if value else 0, ctypes.sizeof(ctypes.c_uint))


@hook("Engine.GameViewportClient:Tick")
def viewport_tick(*_: Any) -> None:
    with contextlib.suppress(StopIteration):
        next(exec_iterator)


@hook("WillowGame.WillowGFxMenuFrontend:OpenSP")
def frontend_intercept(
    _1: UObject, args: WrappedStruct, _3: Any, func: BoundFunction
) -> type[Block]:
    global frontend_func, frontend_args, exec_iterator
    frontend_intercept.disable()
    frontend_func = func
    frontend_args = deepcopy(args)
    exec_iterator = exec_before_play()
    viewport_tick.enable()
    return Block


def exec_before_play() -> Iterator[None]:
    global frontend_func, frontend_args, exec_iterator
    notify_loading_msg.show()
    gfx_object = notify_loading_msg._gfx_object()  # pyright: ignore[reportPrivateUsage]
    if gfx_object is not None:
        gfx_object.ShowTooltips(False)
    yield

    for mod in ALL_TEXT_MODS:
        if gfx_object is not None:
            gfx_object.SetVariableString(TRAINING_BOX_TEXT_VAR, f"{LOADING_MSG}\n\n{mod.name}")
        yield
        for _msg in mod.exec_mod():
            pass

    notify_loading_msg.hide()
    viewport_tick.disable()
    frontend_func(frontend_args)
    del frontend_func, frontend_args, exec_iterator

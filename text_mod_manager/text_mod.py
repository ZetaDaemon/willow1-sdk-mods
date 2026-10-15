from __future__ import annotations

import tomllib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import wraps
from typing import TYPE_CHECKING, Any, overload, override

import unrealsdk
from mods_base import AbstractCommand, Mod, get_pc

from .command_parser import CommandParser

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_COMMANDS: set[str] = set()
_JSON_COMMANDS: set[str] = set()


def register(cmd: AbstractCommand, json: bool = False) -> None:
    name = cmd.cmd
    if name in _COMMANDS:
        msg = f"Command '{name}' already exists!"
        raise ValueError(msg)
    if json:
        _JSON_COMMANDS.add(name)
    _COMMANDS.add(name)


def deregister(cmd: AbstractCommand, json: bool = False) -> None:
    name = cmd.cmd
    if json:
        _JSON_COMMANDS.remove(name)
    _COMMANDS.remove(name)


def autoregister_inner(obj: AbstractCommand | Mod, json: bool = False) -> AbstractCommand | Mod:
    if isinstance(obj, Mod):
        for cmd in obj.commands:
            autoregister_inner(cmd, json)
        return obj

    old_enable = obj.enable
    old_disable = obj.disable

    @wraps(obj.enable)
    def new_enable() -> None:
        old_enable()
        register(obj, json)

    @wraps(obj.disable)
    def new_disable() -> None:
        old_disable()
        deregister(obj, json)

    obj.enable = new_enable
    obj.disable = new_disable

    if obj.is_registered():
        register(obj, json)

    return obj


@overload
def autoregister[C: AbstractCommand](obj: C, /) -> C: ...


@overload
def autoregister(obj: Mod, /) -> Mod: ...
def autoregister(obj: AbstractCommand | Mod, /) -> AbstractCommand | Mod:
    return autoregister_inner(obj)


@overload
def autoregister_json[C: AbstractCommand](obj: C, /) -> C: ...


@overload
def autoregister_json(obj: Mod, /) -> Mod: ...
def autoregister_json(obj: AbstractCommand | Mod, /) -> AbstractCommand | Mod:
    return autoregister_inner(obj, True)


@dataclass
class TextMod(Mod, ABC):
    """ABC that represents a text mod."""

    mod_path: Path = field(kw_only=True)

    def _exec_file(self, file_path: Path) -> None:
        """Run the lines in a file as commands, skipping comments."""
        pc = get_pc()
        with file_path.open("r") as file:
            for line in CommandParser().parse_lines(file.readlines(), _COMMANDS, _JSON_COMMANDS):
                pc.ClientConsoleCommand(line)

    @abstractmethod
    def exec_mod(self) -> Iterator[str]:
        """Exec iterator, returning the current exec status of the mod."""

    @staticmethod
    @abstractmethod
    def extract_metadata(path: Path) -> dict[str, Any]:
        """Read the metadata from the path."""


@dataclass
class FileTextMod(TextMod):
    """Text mod that is only a single file."""

    @override
    def exec_mod(self) -> Iterator[str]:
        """Exec the file."""
        yield "Running File"
        self._exec_file(self.mod_path)

    @override
    @staticmethod
    def extract_metadata(path: Path) -> dict[str, Any]:
        """Extract metadata from the mod file.

        Metadata should be handled through BLIMP tags.
        https://github.com/apple1417/blcmm-parsing/tree/master/blimp
        """
        metadata: dict[str, Any] = {}
        with path.open("r") as file:
            for line in file:
                if not line.startswith("#"):
                    break
                stripped_line = line.lstrip("#").rstrip()
                if not stripped_line.startswith("@"):
                    continue
                key, value = stripped_line.split(" ", maxsplit=1)
                metadata[key[1:]] = value
        return metadata


FOLDER_CONFIG_FILE = "textmod.toml"
UPKS_DIR_NAME = "upks"


@dataclass
class FolderTextMod(TextMod):
    """Text mod that is a folder of files."""

    mod_files: list[Path] = field(init=False, default_factory=list)
    upks: list[Path] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        """Discover all executable files to save time when running the mod."""
        super().__post_init__()
        self.discover_files()

    def discover_files(self) -> None:
        """Find all .blmod files within the folder."""
        self.mod_files = []
        for root, dirs, files in self.mod_path.walk():
            dirs[:] = [d for d in dirs if d != UPKS_DIR_NAME and not d.startswith(".")]
            if root.name == UPKS_DIR_NAME:
                continue
            for file in files:
                if file.startswith("."):
                    continue
                file_path = root / file
                if file_path.suffix != ".blmod":
                    continue
                self.mod_files.append(file_path)

        upks_dir = self.mod_path / UPKS_DIR_NAME
        if not upks_dir.is_dir():
            return
        for root, _dirs, files in upks_dir.walk():
            for file in files:
                file_path = root / file
                if file_path.suffix != ".upk":
                    continue
                self.upks.append(file_path.absolute())

    @override
    def exec_mod(self) -> Iterator[str]:
        """Exec all discovered files."""
        upk_count = len(self.upks)
        for idx, file in enumerate(self.upks):
            yield f"Loading UPKs: {idx / upk_count:.0%}"
            unrealsdk.load_package(str(file))

        file_count = len(self.mod_files)
        for idx, file in enumerate(self.mod_files):
            yield f"Running Files: {idx / file_count:.0%}"
            self._exec_file(file)

    @override
    @staticmethod
    def extract_metadata(path: Path) -> dict[str, Any]:
        """Open the config file and read the metadata."""
        config_path = path / FOLDER_CONFIG_FILE
        if not config_path.is_file():
            return {}

        with config_path.open("rb") as config:
            return tomllib.load(config)

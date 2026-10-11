from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, override

import tomllib

from mods_base import Mod, get_pc

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@dataclass
class TextMod(Mod, ABC):
    """ABC that represents a text mod."""

    mod_path: Path = field(kw_only=True)

    def _exec_file(self, file_path: Path) -> None:
        """Run the lines in a file as commands, skipping comments."""
        pc = get_pc()
        with file_path.open("r") as file:
            for line in file.readlines():
                if line.startswith("#"):
                    continue
                if not line.strip():
                    continue
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


@dataclass
class FolderTextMod(TextMod):
    """Text mod that is a folder of files."""

    mod_files: list[Path] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        """Discover all executable files to save time when running the mod."""
        super().__post_init__()
        self.discover_files()

    def discover_files(self) -> None:
        """Find all .blmod files within the folder."""
        self.mod_files = []
        for root, _dirs, files in self.mod_path.walk():
            for file in files:
                file_path = root / file
                if file_path.suffix != ".blmod":
                    continue
                self.mod_files.append(file_path)

    @override
    def exec_mod(self) -> Iterator[str]:
        """Exec all discovered files."""
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

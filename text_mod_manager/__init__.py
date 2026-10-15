import argparse
from pathlib import Path

from mods_base import Library, build_mod, command

from text_mod_manager import load_manager, text_mod
from text_mod_manager.text_mod import autoregister as autoregister
from text_mod_manager.text_mod import autoregister_json as autoregister_json

TEXT_MODS_DIR = Path(__file__).parent.parent.parent / "text_mods"
ALL_TEXT_MODS: list[text_mod.TextMod] = []


@command()
def re_exec_mods(_args: argparse.Namespace) -> None:
    load_manager.exec_all_mods()


load_manager.find_mods()


build_mod(cls=Library)

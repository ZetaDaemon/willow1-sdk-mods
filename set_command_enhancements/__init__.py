from importlib.util import find_spec

from mods_base import Library, build_mod

from .builtins import set_template, sets

commands = [set_template.set_template, set_template.set_template_create, sets.sets]


if not find_spec("command_extensions"):
    from .ce_replacements import clone, keep_alive, load_package

    commands.extend([clone.clone, keep_alive.keep_alive, load_package.load_package])

build_mod(cls=Library, commands=commands)

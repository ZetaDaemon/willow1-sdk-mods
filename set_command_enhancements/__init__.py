from importlib.util import find_spec

from mods_base import Library, build_mod

from .builtins import construct, set_template, sets

commands = [
    construct.construct,
    set_template.set_template,
    set_template.set_template_create,
    sets.sets,
]
hooks = [sets.post_load]

if not find_spec("command_extensions"):
    from .ce_replacements import clone, keep_alive, load_package, pyb

    commands.extend([clone.clone, keep_alive.keep_alive, load_package.load_package, pyb.pyb])

build_mod(cls=Library, commands=commands, hooks=hooks)

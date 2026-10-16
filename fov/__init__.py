from typing import Any

from mods_base import build_mod, get_pc, hook
from mods_base.options import SliderOption
from unrealsdk.hooks import Block, Type
from unrealsdk.unreal import UObject, notify_changes


@SliderOption("FOV", 70, 10, 130, 10).set_on_change()
def fov(_: SliderOption, new_value: float) -> None:
    pc = get_pc()
    set_default_fov(pc, new_value)
    pc.FixFOV()


vehicle_fov = SliderOption("Vehicle FOV", 80, 10, 170, 10)
afterburner_fov = SliderOption("Afterburner FOV", 110, 10, 170, 10)


def set_default_fov(pc: UObject, value: float) -> None:
    pc.DefaultFOV = value
    pc.PlayerClass.FOV = value
    pc.Class.ClassDefaultObject.DefaultFOV = value


@hook("WillowGame.WillowPlayerController:ApplyCharacterClassDefaults")
def apply_defaults(pc: UObject, *_: Any) -> None:
    set_default_fov(pc, fov.value)


@hook("WillowGame.WillowPlayerController:OnPlayerClassChange")
def class_changed(pc: UObject, *_: Any) -> None:
    set_default_fov(pc, fov.value)


@hook("Engine.PlayerController:FixFOV")
def fix_fov(pc: UObject, *_: Any) -> type[Block]:
    with notify_changes():
        pc.FOVAngle = pc.DefaultFOV
        pc.DesiredFOVBaseValue = pc.DefaultFOV
        pc.DesiredFOV = pc.DefaultFOV
    return Block


@hook("WillowGame.WillowVehicle:PostBeginPlay", Type.POST)
def driver_enter(obj: UObject, *_: Any) -> None:
    obj.DefaultFOV = vehicle_fov.value
    obj.AfterburnerMaxFOV = afterburner_fov.value


build_mod(options=(fov, vehicle_fov, afterburner_fov))

from typing import Any

from mods_base import build_mod, get_pc, hook
from mods_base.options import SliderOption
from unrealsdk.hooks import Block, Type
from unrealsdk.unreal import UObject, notify_changes


@SliderOption("FOV", 70, 10, 130).set_on_change()
def fov_slider(_: SliderOption, new_fov: float) -> None:
    set_player_fov(new_fov)


def set_player_fov(f: float, pc: UObject | None = None) -> None:
    if pc is None:
        pc = get_pc()
    if (camera := pc.PlayerCamera) is not None:
        camera.SetFOV(f)
    with notify_changes():
        pc.FOVAngle = f
        pc.DefaultFOV = f
        pc.DesiredFOVBaseValue = f
        pc.DesiredFOV = f
        default = pc.Class.ClassDefaultObject
        default.FOVAngle = f
        default.DefaultFOV = f
        default.DesiredFOVBaseValue = f
        default.DesiredFOV = f


@hook("WillowGame.WillowPlayerController:ApplyCharacterClassDefaults", Type.POST)
def apply_defaults(pc: UObject, *_: Any) -> None:
    set_player_fov(fov_slider.value, pc)


@hook("WillowGame.WillowPlayerController:OnPlayerClassChange", Type.POST)
def class_changed(pc: UObject, *_: Any) -> None:
    set_player_fov(fov_slider.value, pc)


@hook("Engine.PlayerController:FixFOV")
def fix_fov(pc: UObject, *_: Any) -> type[Block]:
    set_player_fov(fov_slider.value, pc)
    return Block


@hook("Engine.PlayerController:ResetFOV")
def reset_fov(pc: UObject, *_: Any) -> type[Block]:
    set_player_fov(fov_slider.value, pc)
    return Block


@hook("WillowGame.WillowVehicle:DriverLeave", Type.POST)
def driver_leave(*_: Any) -> None:
    set_player_fov(fov_slider.value)


@hook("WillowGame.WillowVehicle:PassengerLeave", Type.POST)
def passenger(*_: Any) -> None:
    set_player_fov(fov_slider.value)


@hook("WillowGame.WillowWeaponPawn:DriverLeave", Type.POST)
def weapon_driver_leave(*_: Any) -> None:
    set_player_fov(fov_slider.value)


build_mod()

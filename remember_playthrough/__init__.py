import json
from typing import Any

import unrealsdk
from mods_base import SETTINGS_DIR, EInputEvent, KeybindOption, build_mod, hook
from ui_utils import OptionBox, OptionBoxButton
from unrealsdk.hooks import Block
from unrealsdk.unreal import UObject, WrappedStruct

SAVES_PLAYTHROUGH_JSON_FILE_NAME = "playthrough_saves.json"
SAVES_PLAYTHROUGH_JSON_FILE = SETTINGS_DIR / SAVES_PLAYTHROUGH_JSON_FILE_NAME

WILLOW_GLOBALS_DEFAULT = unrealsdk.find_class("WillowGlobals").ClassDefaultObject

PT1_NUMBER = 0
PT2_NUMBER = 1

select_playthrough_keybind = KeybindOption("Playthrough Select", "C")

pt1_btn = OptionBoxButton("Playthrough 1")
pt2_btn = OptionBoxButton("Playthrough 2")

lobby_movie: UObject


def on_select_playthrough(_option: OptionBox, button: OptionBoxButton) -> None:
    global lobby_movie
    save_helper = lobby_movie.SaveGameHelper

    row = int(lobby_movie.GetVariableNumber("_root.mMenu.mList.mSelectedItem"))
    tag = lobby_movie.GetVariableString(f"_root.mMenu.mList.item{row}.mMenuTag")
    if not tag or not tag.isdecimal():
        return

    index = int(tag) - 4
    if not 0 <= index < len(save_helper.SaveGames):
        return
    data = save_helper.SaveGames[index]
    filename = str(data.FilePath).replace("\\", "/").rsplit("/", 1)[-1]
    save_id = int(filename[4:-4], 16)

    del lobby_movie
    save_playthrough_for_id(save_id, PT1_NUMBER if button == pt1_btn else PT2_NUMBER)


select_playthrough_option = OptionBox(
    title="Select Playthrough",
    message="Choose the playthrough you wish to load.",
    buttons=[pt1_btn, pt2_btn],
    on_select=on_select_playthrough,
)


def lookup_playthrough_for_id(save_id: int) -> int | None:
    if not SAVES_PLAYTHROUGH_JSON_FILE.exists():
        return None
    with SAVES_PLAYTHROUGH_JSON_FILE.open("r") as file:
        data: dict[str, int] = json.load(file)
        return data.get(str(save_id))


def save_playthrough_for_id(save_id: int, playthrough: int) -> None:
    if not SAVES_PLAYTHROUGH_JSON_FILE.exists():
        data = {}
    else:
        with SAVES_PLAYTHROUGH_JSON_FILE.open("r") as file:
            data: dict[int, int] = json.load(file)
    data[save_id] = playthrough
    with SAVES_PLAYTHROUGH_JSON_FILE.open("w") as file:
        json.dump(data, file)


@hook("WillowGame.WillowGFxLobbySinglePlayer:FinishLoadGame")
def finish_load_game(obj: UObject, *_: Any) -> type[Block] | None:
    profile = (
        WILLOW_GLOBALS_DEFAULT.GetWillowGlobals()
        .GetWillowSaveGameManager()
        .GetCachedPlayerProfile(obj.GetControllerId())
    )
    if profile is None or profile.SaveGameId == -1 or profile.PlaythroughsCompleted == 0:
        return None
    if (playthrough := lookup_playthrough_for_id(profile.SaveGameId)) is None:
        return None
    obj.LaunchSaveGame(playthrough)
    return Block


@hook("WillowGame.WillowGFxLobbySinglePlayer:OnChooseDifficulty_Click")
def choose_difficulty(obj: UObject, args: WrappedStruct, *_: Any) -> None:
    profile = (
        WILLOW_GLOBALS_DEFAULT.GetWillowGlobals()
        .GetWillowSaveGameManager()
        .GetCachedPlayerProfile(obj.GetControllerId())
    )
    if profile is None or profile.SaveGameId == -1:
        return

    pt_number = PT2_NUMBER if args.Dlg.DialogResult == "Dif2" else PT1_NUMBER
    save_playthrough_for_id(profile.SaveGameId, pt_number)


@hook("WillowGame.WillowGFxLobbySinglePlayer:HandleInputKey")
def handle_input(obj: UObject, args: WrappedStruct, *_: Any) -> type[Block] | None:
    global lobby_movie
    if obj.bIsLoading:
        return None
    if args.ukey != select_playthrough_keybind.value or args.uevent != EInputEvent.IE_Pressed:
        return None
    lobby_movie = obj
    select_playthrough_option.show()
    return Block


@hook("WillowGame.WillowGFxLobbyLoadCharacter:SetTipText")
def set_tip_text(obj: UObject, args: WrappedStruct, *_: Any) -> type[Block] | None:
    if obj.Class.Name != "WillowGFxLobbySinglePlayer":
        return None

    string = "<Strings:WillowMenu.bar.BarSelect>     <Strings:WillowMenu.TitleMenu.BackBar>"

    if args.bCanDelete:
        string = f"{string}     [{str(select_playthrough_keybind.value).capitalize()}] PLAYTHROUGH"
        string = f"<Strings:WillowMenu.bar.BarDelete>     {string}"

    if obj.CanShowStorageSelector():
        choose = obj.Caps(obj.Localize("dlgNeedStorageDeviceToLoad", "Choose", "WillowMenu"))
        string = f"<StringAliasMap:GFx_X> {choose}     {string}"

    obj.SetVariableString("lobby.tooltips.text", f"${string}")
    return Block


build_mod(options=[select_playthrough_keybind])

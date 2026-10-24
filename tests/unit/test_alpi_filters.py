"""Unit tests for filter_plugins/alpi.py (pure functions, no Ansible needed)."""

import base64
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "alpi_filters", Path(__file__).resolve().parents[2] / "filter_plugins" / "alpi.py"
)
alpi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(alpi)

CATALOG = {
    "git": {"all": "git"},
    "vim": {"fedora": "vim", "el": "vim-enhanced"},
    "7zip": {"fedora": ["p7zip", "p7zip-plugins"], "el": ["7zip", "7zip-standalone"]},
    "steam": {"fedora": "steam", "el": None},
    "telegram": {"fedora": "telegram-desktop", "el": {"flatpak": "org.telegram.desktop"}},
    "bitwarden": {"all": {"flatpak": "com.bitwarden.desktop"}},
    "fedora_only": {"fedora": "foo"},
    "el10_override": {"el10": "new-name", "el": "old-name"},
    "brave": {"all": "brave-browser", "repo": "brave"},
    "asusctl": {"fedora": ["asusctl", "supergfxctl"], "el": None, "repo": ["asus-linux"]},
    "signal": {"fedora": {"flatpak": "org.signal.Signal"}, "el": "signal-desktop", "repo": "signal"},
    "ffmpeg": {"all": "ffmpeg", "swap": True},
    "mesa-freeworld": {"fedora": ["mesa-va-drivers-freeworld"], "el": None, "swap": True},
    "codecs-flatpak": {"all": {"flatpak": "org.example.Codecs"}, "swap": True},
    "virtualbox": {"fedora": ["VirtualBox", "akmod-VirtualBox"],
                   "el": {"native": ["VirtualBox-7.2", "gcc"], "repo": "virtualbox"}},
    "vendor_both": {"fedora": {"native": "tool", "repo": ["a", "b"]}, "el": "tool", "repo": "entry"},
    # swap per distro: a replacement on one distro only (apt replaces through package metadata)
    "swap_fedora_only": {"fedora": {"native": "ffmpeg", "swap": True}, "el": "ffmpeg"},
    "swap_not_on_el": {"all": "libfoo", "el": {"native": "libfoo", "swap": False}, "swap": True},
    # RPM names under 'rpm', names every distro shares under 'all'
    "sensors": {"rpm": "lm_sensors", "all": "lm-sensors"},
}
ALIASES = {"p7zip": "7zip"}
FEDORA = ["fedora", "rpm", "all"]
EL10 = ["el10", "el", "rpm", "all"]
DEBIAN13 = ["debian13", "debian", "deb", "all"]


def resolve(ids, keys):
    return alpi.alpi_resolve(ids, CATALOG, keys, ALIASES)


class TestResolve:
    def test_native_names_per_distro(self):
        assert resolve(["git", "vim"], FEDORA)["native"] == ["git", "vim"]
        assert resolve(["git", "vim"], EL10)["native"] == ["git", "vim-enhanced"]

    def test_rpm_key_before_all(self):
        assert resolve(["sensors"], FEDORA)["native"] == ["lm_sensors"]
        assert resolve(["sensors"], EL10)["native"] == ["lm_sensors"]
        assert resolve(["sensors"], DEBIAN13)["native"] == ["lm-sensors"]

    def test_list_values_expand(self):
        assert resolve(["7zip"], EL10)["native"] == ["7zip", "7zip-standalone"]

    def test_flatpak_values(self):
        out = resolve(["telegram", "bitwarden"], EL10)
        assert out["flatpak"] == ["org.telegram.desktop", "com.bitwarden.desktop"]
        assert out["native"] == []

    def test_same_id_native_on_one_distro_flatpak_on_another(self):
        assert resolve(["telegram"], FEDORA)["native"] == ["telegram-desktop"]

    def test_null_means_unavailable(self):
        out = resolve(["steam"], EL10)
        assert out["unavailable"] == ["steam"]
        assert out["native"] == []

    def test_unknown_id(self):
        assert resolve(["nope"], FEDORA)["unknown"] == ["nope"]

    def test_missing_key_is_a_catalog_bug(self):
        out = resolve(["fedora_only"], EL10)
        assert out["missing"] == ["fedora_only"]
        assert out["native"] == []

    def test_most_specific_key_wins(self):
        assert resolve(["el10_override"], EL10)["native"] == ["new-name"]
        assert resolve(["el10_override"], ["el", "all"])["native"] == ["old-name"]

    def test_aliases(self):
        assert resolve(["p7zip"], FEDORA)["native"] == ["p7zip", "p7zip-plugins"]

    @pytest.mark.parametrize(
        "item, kind, name",
        [("pkg:sqlitebrowser", "native", "sqlitebrowser"), ("flatpak:org.gimp.GIMP", "flatpak", "org.gimp.GIMP")],
    )
    def test_raw_prefixes_bypass_the_catalog(self, item, kind, name):
        assert resolve([item], FEDORA)[kind] == [name]

    def test_unknown_prefix_is_an_unknown_id(self):
        assert resolve(["rpm:foo"], FEDORA)["unknown"] == ["rpm:foo"]

    def test_duplicates_removed_order_kept(self):
        assert resolve(["vim", "git", "vim", "pkg:git"], FEDORA)["native"] == ["vim", "git"]

    def test_empty_input(self):
        assert resolve(None, FEDORA) == {
            "native": [], "flatpak": [], "pipx": [], "upstream": [], "unknown": [], "missing": [],
            "unavailable": [], "repos": [], "swap": []
        }

    def test_repo_of_a_resolved_package(self):
        assert resolve(["brave", "git"], EL10)["repos"] == ["brave"]

    def test_repo_lists(self):
        assert resolve(["asusctl"], FEDORA)["repos"] == ["asus-linux"]

    def test_no_repo_when_unavailable(self):
        assert resolve(["asusctl"], EL10)["repos"] == []

    def test_no_repo_for_a_flatpak_value(self):
        assert resolve(["signal"], FEDORA)["repos"] == []
        assert resolve(["signal"], EL10)["repos"] == ["signal"]

    def test_repos_deduplicated(self):
        assert resolve(["brave", "brave"], FEDORA)["repos"] == ["brave"]

    def test_per_distro_repo_only_where_named(self):
        assert resolve(["virtualbox"], FEDORA)["repos"] == []
        out = resolve(["virtualbox"], EL10)
        assert out["native"] == ["VirtualBox-7.2", "gcc"] and out["repos"] == ["virtualbox"]

    def test_per_distro_repo_replaces_the_entry_repo(self):
        assert resolve(["vendor_both"], FEDORA) == dict(resolve([], FEDORA), native=["tool"], repos=["a", "b"])
        assert resolve(["vendor_both"], EL10)["repos"] == ["entry"]

    def test_swap_names_are_also_native(self):
        out = resolve(["git", "ffmpeg", "mesa-freeworld"], FEDORA)
        assert out["swap"] == ["ffmpeg", "mesa-va-drivers-freeworld"]
        assert out["native"] == ["git", "ffmpeg", "mesa-va-drivers-freeworld"]

    def test_no_swap_when_unavailable(self):
        out = resolve(["mesa-freeworld"], EL10)
        assert out["swap"] == [] and out["unavailable"] == ["mesa-freeworld"]

    def test_no_swap_for_flatpaks_or_raw_names(self):
        assert resolve(["codecs-flatpak", "pkg:ffmpeg"], FEDORA)["swap"] == []

    def test_swap_in_a_per_distro_value(self):
        assert resolve(["swap_fedora_only"], FEDORA)["swap"] == ["ffmpeg"]
        out = resolve(["swap_fedora_only"], EL10)
        assert out["swap"] == [] and out["native"] == ["ffmpeg"]

    def test_per_distro_swap_overrides_the_entry_swap(self):
        assert resolve(["swap_not_on_el"], FEDORA)["swap"] == ["libfoo"]
        out = resolve(["swap_not_on_el"], EL10)
        assert out["swap"] == [] and out["native"] == ["libfoo"] and out["repos"] == []


class TestRepos:
    DEFS = {"epel": {"type": "package"}, "crb": {"type": "dnf_config"}, "brave": {"type": "yum"}}

    def test_always_first_in_order_then_needed(self):
        out = alpi.alpi_repos(self.DEFS, ["crb", "epel"], ["brave", "epel"])
        assert [r["id"] for r in out["enabled"]] == ["crb", "epel", "brave"]
        assert out["enabled"][0] == {"type": "dnf_config", "id": "crb"}
        assert out["unknown"] == []

    def test_unknown_repo_ids(self):
        assert alpi.alpi_repos(self.DEFS, [], ["nope"])["unknown"] == ["nope"]

    def test_definitions_not_modified(self):
        alpi.alpi_repos(self.DEFS, ["epel"], [])
        assert "id" not in self.DEFS["epel"]


class TestCanonical:
    def test_maps_aliases_and_keeps_the_rest(self):
        assert alpi.alpi_canonical(["p7zip", "git", "pkg:x"], ALIASES) == ["7zip", "git", "pkg:x"]

    def test_no_aliases(self):
        assert alpi.alpi_canonical(["git"]) == ["git"]


class TestFeatures:
    HW = ["nvidia", "asus"]

    @pytest.mark.parametrize(
        "value, detected, expected",
        [("auto", True, True), ("auto", False, False), (True, False, False), (False, True, False)],
    )
    def test_hardware_follows_detection_and_can_only_be_vetoed(self, value, detected, expected):
        out = alpi.alpi_features({"nvidia": value}, self.HW, {"nvidia": detected})
        assert out["nvidia"] is expected

    def test_plain_features_are_booleans(self):
        out = alpi.alpi_features({"steam": True, "clamav": False}, self.HW, {})
        assert out == {"steam": True, "clamav": False}

    def test_feature_ids_only_for_features_that_are_on(self):
        pkgs = {"steam": ["steam"], "asus": ["asusctl", "supergfxctl"], "vbox": ["virtualbox"]}
        flags = {"steam": True, "asus": False, "vbox": True}
        assert alpi.alpi_feature_ids(pkgs, flags) == ["steam", "virtualbox"]

    def test_feature_ids_ignore_unknown_flags(self):
        assert alpi.alpi_feature_ids({"x": ["a"]}, {}) == []

    def test_filters_are_registered(self):
        assert set(alpi.FilterModule().filters()) == {
            "alpi_resolve", "alpi_canonical", "alpi_features", "alpi_repos", "alpi_feature_ids",
            "alpi_flatpak_overrides", "alpi_cedilla_xwayland", "alpi_zram_plan", "alpi_xwayland_entries", "alpi_luks_aliases", "alpi_invalid_luks", "alpi_pipx_name",
            "alpi_appimage_release", "alpi_github_release", "alpi_upstream_missing",
        }


# --- alpi_flatpak_overrides --------------------------------------------------------------------

BW = "com.bitwarden.desktop"
ZOOM = "us.zoom.Zoom"
ZAP = "com.rtosta.zapzap"


def test_flatpak_overrides_merge_layers_and_folders_in_order():
    res = alpi.alpi_flatpak_overrides(
        [{BW: ["--socket=wayland", "--nosocket=x11"]}, {BW: ["--socket=wayland", "--env=A=1"]}],
        {BW: ["/srv/wks:ro"]},
        [BW],
    )
    assert res == {"apply": [{"app": BW, "flags": ["--socket=wayland", "--nosocket=x11", "--env=A=1",
                                                   "--filesystem=/srv/wks:ro"], "reset_if": ""}],
                   "skipped": [], "invalid": []}


def test_flatpak_overrides_only_for_selected_apps():
    res = alpi.alpi_flatpak_overrides([{BW: ["--socket=wayland"], ZOOM: ["--socket=wayland"]}],
                                      {ZAP: ["/srv/wks:ro"]}, [BW, ZAP])
    assert [a["app"] for a in res["apply"]] == [BW, ZAP]
    assert res["skipped"] == [ZOOM]


def test_flatpak_overrides_report_flags_without_dashes_even_when_skipped():
    res = alpi.alpi_flatpak_overrides([{BW: ["socket=wayland"], ZOOM: ["-x"]}], {}, [BW])
    assert res["invalid"] == [f"{BW}: socket=wayland", f"{ZOOM}: -x"]


@pytest.mark.parametrize("layers, filesystem", [(None, None), ([None, {}], {}), ([{BW: None}], {BW: []})])
def test_flatpak_overrides_empty_inputs(layers, filesystem):
    assert alpi.alpi_flatpak_overrides(layers, filesystem, [BW]) == {"apply": [], "skipped": [], "invalid": []}


def test_flatpak_overrides_reset_if_for_selected_apps_even_without_flags():
    res = alpi.alpi_flatpak_overrides([{BW: ["--socket=wayland"]}], {}, [BW, ZAP],
                                      {BW: ".XCompose", ZAP: ".XCompose", ZOOM: ".XCompose"})
    assert res["apply"] == [{"app": BW, "flags": ["--socket=wayland"], "reset_if": ".XCompose"},
                            {"app": ZAP, "flags": [], "reset_if": ".XCompose"}]
    assert res["skipped"] == [ZOOM]


# --- alpi_cedilla_xwayland ---------------------------------------------------------------------

@pytest.mark.parametrize(
    "setting, is_kde, kwin, expected",
    [
        ("auto", True, "6.6.4", True),
        ("auto", True, "6.7.5", False),
        ("auto", True, "6.10.0", False),   # numeric, not string, comparison
        ("auto", True, "5.27.11", True),
        ("auto", True, "", False),         # KWin not installed
        ("auto", False, "6.6.4", False),   # not a KDE session
        (True, True, "6.7.5", True),
        (True, False, "6.6.4", False),     # forced on KDE only
        (False, True, "6.6.4", False),
    ],
)
def test_cedilla_xwayland(setting, is_kde, kwin, expected):
    assert alpi.alpi_cedilla_xwayland(setting, is_kde, kwin, "6.7") is expected


# --- alpi_xwayland_entries ---------------------------------------------------------------------

FLAG = "--ozone-platform=x11"
MARK = "ALPI: XWayland copy"
SYS = "[Desktop Entry]\nName=Code\nExec=/usr/share/code/code %F\n[Desktop Action new]\nExec=/usr/share/code/code --new-window %F\n"
SYS_X11 = SYS.replace("code/code ", "code/code " + FLAG + " ")
OWN = "[Desktop Entry]\nName=My Code\nExec=/opt/code/code\n"


def _slurp(name, text):
    return {"item": name} if text is None else {"item": name, "content": base64.b64encode(text.encode()).decode()}


def plan(sys_text, usr_text, enabled):
    return alpi.alpi_xwayland_entries([_slurp("c.desktop", sys_text)], [_slurp("c.desktop", usr_text)],
                                      FLAG, enabled, MARK)


def test_xwayland_on_copies_the_system_entry_with_the_flag_and_marker():
    assert plan(SYS, None, True) == [{"name": "c.desktop", "state": "present",
                                      "content": f"# {MARK}\n" + SYS_X11}]


def test_xwayland_on_is_stable_and_rebuilds_ours_from_the_system_entry():
    ours = f"# {MARK}\n" + SYS_X11
    assert plan(SYS, ours, True) == []
    newer = SYS.replace("Name=Code", "Name=Code 2")
    assert plan(newer, ours, True)[0]["content"] == f"# {MARK}\n" + SYS_X11.replace("Name=Code", "Name=Code 2")


def test_xwayland_on_adds_the_flag_once_to_a_users_own_copy():
    res = plan(SYS, OWN, True)
    assert res == [{"name": "c.desktop", "state": "present", "content": OWN.replace("code/code", "code/code " + FLAG)}]
    assert plan(SYS, res[0]["content"], True) == []


def test_xwayland_aapi_copy_without_marker_is_ours():
    assert plan(SYS, SYS_X11, True)[0]["content"] == f"# {MARK}\n" + SYS_X11
    assert plan(SYS, SYS_X11, False) == [{"name": "c.desktop", "state": "absent", "content": ""}]


def test_xwayland_off_removes_ours_and_strips_the_flag_from_the_users_own():
    assert plan(SYS, f"# {MARK}\n" + SYS_X11, False) == [{"name": "c.desktop", "state": "absent", "content": ""}]
    own_x11 = OWN.replace("code/code", "code/code " + FLAG)
    assert plan(SYS, own_x11, False) == [{"name": "c.desktop", "state": "present", "content": OWN}]
    assert plan(SYS, OWN, False) == []


def test_xwayland_nothing_without_the_app():
    assert plan(None, None, True) == []
    assert plan(None, None, False) == []
    assert plan(None, f"# {MARK}\n" + SYS_X11, True) == [{"name": "c.desktop", "state": "absent", "content": ""}]
    assert plan(None, OWN, True) == [{"name": "c.desktop", "state": "present", "content": OWN.replace("code/code", "code/code " + FLAG)}]


# --- alpi_luks_aliases ---------------------------------------------------------------------------

UUID = "ad99f7e6-cf3a-4581-9c46-de99119b00d4"


def test_luks_aliases_by_uuid():
    assert alpi.alpi_luks_aliases({"thevoid": UUID}).splitlines() == [
        f'alias open-thevoid="udisksctl unlock -b /dev/disk/by-uuid/{UUID}; '
        f'udisksctl mount -b /dev/mapper/luks-{UUID}"',
        f'alias close-thevoid="udisksctl unmount -b /dev/mapper/luks-{UUID}; '
        f'udisksctl lock -b /dev/disk/by-uuid/{UUID}"',
    ]


@pytest.mark.parametrize("volumes", [None, {}])
def test_luks_aliases_empty(volumes):
    assert alpi.alpi_luks_aliases(volumes) == ""


@pytest.mark.parametrize("volumes, bad", [
    ({"thevoid": UUID, "data_2": UUID.upper()}, []),
    ({"the void": UUID}, [f"the void: {UUID}"]),
    ({"x": "not-a-uuid", "y": UUID + "; rm"}, ["x: not-a-uuid", f"y: {UUID}; rm"]),
    ({"nl": UUID + "\n"}, [f"nl: {UUID}\n"]),
    (None, []),
])
def test_invalid_luks(volumes, bad):
    assert alpi.alpi_invalid_luks(volumes) == bad


# --- pipx --------------------------------------------------------------------------------------

PIPX_CATALOG = {
    "markitdown": {"all": {"pipx": "markitdown[all]"}},
    "tool_el": {"fedora": {"pipx": "tool"}, "el": None},
}


def test_resolve_pipx_entries_and_raw_prefix():
    res = alpi.alpi_resolve(["markitdown", "pipx:cowsay==6.1", "tool_el"], PIPX_CATALOG, EL10)
    assert res["pipx"] == ["markitdown[all]", "cowsay==6.1"]
    assert res["native"] == [] and res["flatpak"] == [] and res["repos"] == []
    assert res["unavailable"] == ["tool_el"]


def test_resolve_upstream_entries_per_distro():
    catalog = {"roboto": {"fedora": "google-roboto-fonts", "el": {"upstream": "roboto"}},
               "both": {"all": {"upstream": "src"}}}
    res = alpi.alpi_resolve(["roboto", "both", "roboto"], catalog, EL10)
    assert res["upstream"] == ["roboto", "src"]
    assert res["native"] == [] and res["unavailable"] == [] and res["repos"] == []
    res = alpi.alpi_resolve(["roboto"], catalog, FEDORA)
    assert res["native"] == ["google-roboto-fonts"] and res["upstream"] == []


@pytest.mark.parametrize("spec, name", [
    ("markitdown[all]", "markitdown"), ("notebooklm-py[browser]", "notebooklm-py"),
    ("pdf2docx", "pdf2docx"), ("cowsay==6.1", "cowsay"), ("x>=1; python_version>'3'", "x"),
    (" spaced ", "spaced"),
])
def test_pipx_name(spec, name):
    assert alpi.alpi_pipx_name(spec) == name


# The real manifest's shape (2.22.0, 2026-10-10): a .deb next to the AppImage, sha512 in base64
SHA = bytes(range(64))
MANIFEST = {
    "version": "2.22.0",
    "files": [
        {"url": "https://example.org/2.22.0/Antigravity.deb", "sha512": base64.b64encode(b"x" * 64).decode()},
        {"url": "https://example.org/2.22.0/Antigravity.AppImage", "sha512": base64.b64encode(SHA).decode()},
    ],
    "path": "Antigravity.AppImage",
}


def test_appimage_release_picks_the_appimage_with_a_hex_checksum():
    assert alpi.alpi_appimage_release(MANIFEST) == {
        "version": "2.22.0", "url": "https://example.org/2.22.0/Antigravity.AppImage", "sha512": SHA.hex()}


@pytest.mark.parametrize("manifest, error", [
    (None, "no AppImage"), ("not a mapping", "no AppImage"), ({"files": []}, "no AppImage"),
    ({"files": [MANIFEST["files"][0]]}, "no AppImage"),
    ({"files": [{"url": "a/x.AppImage"}]}, "no valid sha512"),
    ({"files": [{"url": "a/x.AppImage", "sha512": "not base64!"}]}, "no valid sha512"),
    ({"files": [{"url": "a/x.AppImage", "sha512": base64.b64encode(b"short").decode()}]}, "no valid sha512"),
])
def test_appimage_release_errors(manifest, error):
    assert error in alpi.alpi_appimage_release(manifest)["error"]


# The real release's shape (roboto-3-classic v3.016, 2026-10-10)
DIGEST = "sha256:" + "ab" * 32
RELEASE = {"tag_name": "v3.016", "assets": [
    {"name": "Roboto_v3.016.zip", "digest": DIGEST,
     "browser_download_url": "https://example.org/v3.016/Roboto_v3.016.zip"},
    {"name": "notes.txt", "browser_download_url": "https://example.org/notes.txt"},
]}


def test_github_release_picks_the_matching_asset():
    assert alpi.alpi_github_release(RELEASE, "[.]zip$") == {
        "tag": "v3.016", "name": "Roboto_v3.016.zip",
        "url": "https://example.org/v3.016/Roboto_v3.016.zip", "checksum": DIGEST}


@pytest.mark.parametrize("digest", [None, "", "sha512:" + "ab" * 64, "sha256:short", "md5:x"])
def test_github_release_without_a_usable_digest(digest):
    release = {"tag_name": "v1", "assets": [{"name": "a.zip", "digest": digest, "browser_download_url": "u"}]}
    assert alpi.alpi_github_release(release, "zip$")["checksum"] == ""


@pytest.mark.parametrize("release, pattern, error", [
    (None, "zip$", "no tag_name"), ({"assets": []}, "zip$", "no tag_name"),
    (RELEASE, "[.]tar[.]gz$", "no asset matching"), ({"tag_name": "v1"}, "zip$", "no asset matching"),
    ({"tag_name": "v1", "assets": [{"name": "a.zip"}]}, "zip$", "no asset matching"),
    (RELEASE, "(", "bad asset pattern"),
])
def test_github_release_errors(release, pattern, error):
    assert error in alpi.alpi_github_release(release, pattern)["error"]


def test_upstream_missing_decides_only_on_answers():
    import json
    sources = {"ok": {"asset": "zip$"}, "moved": {"asset": "zip$"}, "noasset": {"asset": "tar$"},
               "down": {"asset": "zip$"}, "limited": {"asset": "zip$"}, "garbled": {"asset": "zip$"}}
    results = [
        {"item": "ok", "status": 200, "content": json.dumps(RELEASE)},
        {"item": "moved", "status": 404},
        {"item": "noasset", "status": 200, "content": json.dumps(RELEASE)},
        {"item": "down", "status": -1},
        {"item": "limited", "status": 403, "content": "{}"},
        {"item": "garbled", "status": 200, "content": "<html>"},
    ]
    assert alpi.alpi_upstream_missing(results, sources) == ["moved", "noasset", "garbled"]
    assert alpi.alpi_upstream_missing(None, {}) == []


# alpi_zram_plan: swapon --raw --bytes lines (NAME TYPE SIZE PRIO)
GIB = 2**30
ZRAM0 = f"/dev/zram0 partition {8 * GIB} 100"
SWAPFILE = f"/swap/swapfile file {4 * GIB} -2"
MARKER = "Managed by ALPI"


def _conf(text):
    return {"content": base64.b64encode(text.encode()).decode()}


def zram_plan(setting="auto", swaps="", zswap="N", generator=True, etc_conf=None,
              hibernate=False, mem_mb=32768):
    return alpi.alpi_zram_plan(setting, swaps, zswap, generator, etc_conf or {"failed": True},
                               MARKER, hibernate, mem_mb)


@pytest.mark.parametrize("swaps,generator", [("", False), (ZRAM0, True), (SWAPFILE, False)])
def test_zram_auto_is_on_without_conflicts(swaps, generator):
    plan = zram_plan(swaps=swaps, generator=generator)
    assert plan["state"] == "on" and plan["error"] == "" and not plan["mask"]


def test_zram_swaps_are_split_into_zram_and_disk():
    plan = zram_plan(swaps=ZRAM0 + "\n" + SWAPFILE + "\n/dev/my\\x20disk partition 1024 -3")
    assert [d["name"] for d in plan["zram"]] == ["/dev/zram0"]
    assert plan["disk"] == [{"name": "/swap/swapfile", "type": "file", "size": 4 * GIB, "prio": -2},
                            {"name": "/dev/my disk", "type": "partition", "size": 1024, "prio": -3}]
    assert any("zram (priority 100) is used first" in n for n in plan["notes"])


def test_zram_summary():
    assert zram_plan(mem_mb=16384)["summary"] == ["RAM 16.0 GiB", "no swap", "zram: on"]
    assert zram_plan(swaps=ZRAM0)["summary"][1] == "zram /dev/zram0: 8.0 GiB, priority 100"


def test_zram_off_masks_only_with_the_generator():
    assert zram_plan(False, swaps=ZRAM0)["mask"] is True
    off = zram_plan(False, generator=False)
    assert off["state"] == "off" and off["mask"] is False


def test_zram_own_mask_is_recognized():
    plan = zram_plan(etc_conf=_conf(f"# {MARKER}\n"))
    assert plan["state"] == "on" and plan["own_mask"]


@pytest.mark.parametrize("kwargs,why", [
    ({"etc_conf": _conf("[zram0]\nzram-size = ram\n")}, "your own zram configuration"),
    ({"swaps": ZRAM0, "generator": False}, "set up by something other than zram-generator"),
    ({"zswap": "Y\n"}, "zswap is on"),
])
def test_zram_conflicts_skip_on_auto_and_fail_when_forced(kwargs, why):
    auto = zram_plan(**kwargs)
    assert auto["state"] == "skip" and auto["error"] == ""
    assert any(why in n and "leaves it alone" in n for n in auto["notes"])
    forced = zram_plan(True, **kwargs)
    assert forced["state"] == "skip" and why in forced["error"]
    assert forced["error"].startswith("zram: true cannot be applied")


def test_zram_false_with_zswap_is_just_off():
    assert zram_plan(False, zswap="Y")["state"] == "off"


def test_zram_own_config_beats_false():
    plan = zram_plan(False, etc_conf=_conf("[zram0]\n"))
    assert plan["state"] == "skip" and plan["error"].startswith("zram: false cannot be applied")


@pytest.mark.parametrize("swaps,hibernate,expected", [
    ("", True, True),
    (SWAPFILE, True, True),                       # 4 GiB < 32 GiB of RAM
    (f"/swap/swapfile file {40 * GIB} -2", True, False),
    (ZRAM0, True, True),                          # zram does not count
    ("", False, False),
])
def test_zram_hibernate_reminder(swaps, hibernate, expected):
    assert zram_plan(swaps=swaps, hibernate=hibernate)["hibernate_reminder"] is expected

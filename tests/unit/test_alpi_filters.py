"""Unit tests for filter_plugins/alpi.py (pure functions, no Ansible needed)."""

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
                   "el": {"native": ["VirtualBox-7.2", "gcc"], "repo": "virtualbox-oracle"}},
    "vendor_both": {"fedora": {"native": "tool", "repo": ["a", "b"]}, "el": "tool", "repo": "entry"},
}
ALIASES = {"p7zip": "7zip"}
FEDORA = ["fedora", "all"]
EL10 = ["el10", "el", "all"]


def resolve(ids, keys):
    return alpi.alpi_resolve(ids, CATALOG, keys, ALIASES)


class TestResolve:
    def test_native_names_per_distro(self):
        assert resolve(["git", "vim"], FEDORA)["native"] == ["git", "vim"]
        assert resolve(["git", "vim"], EL10)["native"] == ["git", "vim-enhanced"]

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
            "native": [], "flatpak": [], "unknown": [], "missing": [], "unavailable": [], "repos": [], "swap": []
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
        assert out["native"] == ["VirtualBox-7.2", "gcc"] and out["repos"] == ["virtualbox-oracle"]

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
            "alpi_flatpak_overrides",
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
                                                   "--filesystem=/srv/wks:ro"]}],
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

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
        assert resolve(None, FEDORA) == {"native": [], "flatpak": [], "unknown": [], "missing": [], "unavailable": []}


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

    def test_filters_are_registered(self):
        assert set(alpi.FilterModule().filters()) == {"alpi_resolve", "alpi_canonical", "alpi_features"}

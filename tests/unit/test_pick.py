"""Unit tests for pick.py (the package picker), with the repository's real data and a fake
/etc/os-release. Nothing reads the host's system."""

import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("alpi_pick", ROOT / "pick.py")
pick = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pick)
filters = pick._load_filters(ROOT)

OS_RELEASE = {
    "fedora": 'ID=fedora\nVERSION_ID=44\nPRETTY_NAME="Fedora Linux 44"\n',
    "el10": 'ID="almalinux"\nVERSION_ID="10.0"\nPRETTY_NAME="AlmaLinux 10.0"\n',
    "debian": 'ID=debian\nVERSION_ID="13"\nPRETTY_NAME="Debian GNU/Linux 13"\n',
}


def real_choices(distro, major, des=()):
    data = pick.load_data(ROOT, distro, major)
    return data, pick.choices(data, set(des), filters)


def ids(items):
    return [c.id for c in items]


# --- What is listed -------------------------------------------------------------------------


def test_fedora_lists_everything_but_hardware_and_feature_packages():
    data, (features, packages) = real_choices("Fedora", "44")
    assert ids(features) == ["steam", "clamav", "virtualbox"]
    assert all(c.default for c in features)
    owned = {i for v in data["feature_packages"].values() for i in v}
    assert not owned & set(ids(packages))
    assert {"vim", "chkrootkit", "multimedia", "telegram"} <= set(ids(packages))


def test_el10_hides_unavailable_ids_and_empty_features():
    _, (features, packages) = real_choices("AlmaLinux", "10")
    assert "steam" not in ids(features)
    assert not {"chkrootkit", "unhide", "argyllcms", "google-roboto-fonts", "multimedia"} & set(ids(packages))
    labels = {c.id: c.label for c in packages}
    assert labels["telegram"].endswith("flatpak org.telegram.desktop")
    assert labels["vim"].endswith("vim-enhanced")


@pytest.mark.parametrize("xdg, shown, hidden", [
    ("KDE", "ktorrent", "gnome-tweaks"),
    ("ubuntu:GNOME", "gnome-tweaks", "ktorrent"),
    ("", None, "ktorrent"),
])
def test_only_the_running_desktop_is_listed(xdg, shown, hidden):
    _, (_, packages) = real_choices("Fedora", "44", pick.desktops(xdg))
    if shown:
        assert next(c for c in packages if c.id == shown).default
    assert hidden not in ids(packages)


def test_defaults_match_the_playbook_lists():
    data, (_, packages) = real_choices("Fedora", "44", {"kde"})
    expected = set(data["packages_base"] + data["packages_os"] + data["packages_kde"])
    assert {c.id for c in packages if c.default} == expected


def test_sections_come_from_the_catalog_comments():
    sections = pick.catalog_sections(ROOT / "group_vars" / "all" / "catalog.yml")
    assert sections["vim"] == "Command line and system tools"
    assert sections["zoom"] == "Flatpaks"


# --- Selection as differences from the defaults ---------------------------------------------

FEATURES = [pick.Choice("steam", "", True), pick.Choice("extra", "", False)]
PACKAGES = [pick.Choice("vim", "", True), pick.Choice("git", "", True), pick.Choice("gimp", "", False)]
CATALOG = {"vim": {}, "git": {}, "gimp": {}, "ktorrent": {}}


def test_selection_stores_only_differences():
    sel, dropped = pick.selection(FEATURES, PACKAGES, {"extra"}, {"git", "gimp"}, {}, CATALOG)
    assert sel == {"packages_selection_add": ["gimp"], "packages_selection_skip": ["vim"],
                   "features_selection": {"steam": False, "extra": True}}
    assert dropped == []


def test_unchanged_defaults_give_an_empty_selection():
    sel, _ = pick.selection(FEATURES, PACKAGES, {"steam"}, {"vim", "git"}, {}, CATALOG)
    assert sel == {"packages_selection_add": [], "packages_selection_skip": [], "features_selection": {}}


def test_saved_entries_for_ids_not_listed_are_kept_and_unknown_ones_dropped():
    saved = {"packages_selection_skip": ["ktorrent", "vim", "gone"], "features_selection": {"other": False}}
    sel, dropped = pick.selection(FEATURES, PACKAGES, {"steam"}, {"vim", "git"}, saved, CATALOG)
    # vim is listed and checked now: no longer skipped; ktorrent (another desktop) is kept
    assert sel["packages_selection_skip"] == ["ktorrent"]
    assert sel["features_selection"] == {"other": False}
    assert dropped == ["gone"]


def test_initial_applies_a_saved_selection_through_aliases():
    saved = {"packages_selection_skip": ["vim-old"], "packages_selection_add": ["gimp"],
             "features_selection": {"steam": False}}
    feats_on, pkgs_on = pick.initial(FEATURES, PACKAGES, saved, {"vim-old": "vim"})
    assert feats_on == set()
    assert pkgs_on == {"git", "gimp"}


def test_round_trip_through_the_file(tmp_path):
    sel, _ = pick.selection(FEATURES, PACKAGES, set(), {"vim"}, {}, CATALOG)
    pick.write_selection(tmp_path / "h" / "selection.yml", sel)
    text = (tmp_path / "h" / "selection.yml").read_text()
    assert text.startswith("---\n# Written by pick.py")
    assert pick.initial(FEATURES, PACKAGES, yaml.safe_load(text)) == (set(), {"vim"})


# --- Text interface -------------------------------------------------------------------------


@pytest.mark.parametrize("line, expected", [
    ("vim", {"git"}),               # toggle off
    ("gimp 1", {"git", "gimp"}),    # toggle on, number toggles vim off
    ("+vim -git +gimp", {"vim", "gimp"}),
    ("-gimp +git", {"vim", "git"}), # already in that state
])
def test_parse_toggles(line, expected):
    assert pick.parse_toggles(line, PACKAGES, {"vim", "git"}) == (expected, [])


def test_parse_toggles_applies_nothing_when_a_token_is_unknown():
    assert pick.parse_toggles("-vim nope 9", PACKAGES, {"vim"}) == ({"vim"}, ["nope", "9"])


def test_text_pick_asks_again_after_unknown_ids():
    answers = iter(["-vim nope", "-vim", ""])
    out = []
    result = pick.text_pick("T", PACKAGES, {"vim", "git"}, read=lambda _: next(answers), write=out.append)
    assert result == {"git"}
    assert "Unknown: nope. Nothing changed." in out


# --- End to end -----------------------------------------------------------------------------


def run_main(tmp_path, monkeypatch, distro, answers, xdg=""):
    (tmp_path / "os-release").write_text(OS_RELEASE[distro])
    feed = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _="": next(feed))
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", xdg)
    out = tmp_path / "selection.yml"
    rc = pick.main(["--ui", "text", "--os-release", str(tmp_path / "os-release"), "--output", str(out)])
    return rc, (yaml.safe_load(out.read_text()) if out.exists() else None)


def test_main_writes_the_selection_and_keeps_it_on_the_next_run(tmp_path, monkeypatch):
    rc, sel = run_main(tmp_path, monkeypatch, "fedora", ["-steam", "", "-tmux +chkrootkit", ""])
    assert rc == 0
    assert sel == {"packages_selection_add": [], "packages_selection_skip": ["tmux"],
                   "features_selection": {"steam": False}}
    # Second run, on EL with KDE: Steam is not listed there, its saved veto stays
    rc, sel = run_main(tmp_path, monkeypatch, "el10", ["", "-ktorrent", ""], xdg="KDE")
    assert sel == {"packages_selection_add": [], "packages_selection_skip": ["tmux", "ktorrent"],
                   "features_selection": {"steam": False}}


def test_main_rejects_an_unsupported_distro(tmp_path, monkeypatch):
    rc, sel = run_main(tmp_path, monkeypatch, "debian", [])
    assert rc == 1 and sel is None

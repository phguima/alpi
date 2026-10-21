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
    assert ids(features) == ["steam", "clamav", "virtualbox", "claude_code", "antigravity_cli",
                             "antigravity_ide"]
    assert all(c.default for c in features)
    owned = {i for v in data["feature_packages"].values() for i in v}
    assert not owned & set(ids(packages))
    assert {"vim", "chkrootkit", "multimedia", "telegram"} <= set(ids(packages))


def test_features_without_packages_are_listed_with_their_description():
    # The AI tools install no catalog packages: listed everywhere, labelled from
    # picker_descriptions like the rest
    for distro, major in (("Fedora", "44"), ("AlmaLinux", "10")):
        data, (features, _) = real_choices(distro, major)
        labels = {c.id: c.label for c in features}
        for name in ("claude_code", "antigravity_cli", "antigravity_ide", "clamav"):
            assert labels[name] == data["picker_descriptions"][name]


def test_el10_hides_unavailable_ids_and_empty_features():
    _, (features, packages) = real_choices("AlmaLinux", "10")
    assert "steam" not in ids(features)
    assert not {"chkrootkit", "unhide", "argyllcms", "multimedia"} & set(ids(packages))
    labels = {c.id: c.label for c in packages}
    # Not packaged for EL, installed from Flathub or upstream instead: listed, and labelled so
    assert labels["google-roboto-fonts"] == "Roboto font (upstream release)"
    assert labels["telegram"] == "Telegram messaging (Flathub)"
    assert labels["vim"] == "Vim editor"


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


def test_an_id_without_a_description_lists_its_packages():
    data = {"alpi_catalog": {"gimp": {"all": "gimp"}}, "alpi_catalog_keys": ["all"]}
    _, packages = pick.choices(data, set(), filters)
    assert packages[0].label == "gimp"


# --- Groups ---------------------------------------------------------------------------------


@pytest.mark.parametrize("distro, major, des", [
    ("Fedora", "44", {"gnome"}), ("Fedora", "44", {"kde"}),
    ("AlmaLinux", "10", {"gnome"}), ("AlmaLinux", "10", {"kde"}),
])
def test_every_listed_id_has_a_group_and_a_description(distro, major, des):
    data, (features, packages) = real_choices(distro, major, des)
    grouped = pick.groups(data, features + packages)
    assert "Other" not in dict(grouped)
    assert all(members for _, members in grouped)
    for c in features + packages:
        assert c.id in data["picker_descriptions"], c.id


def test_picker_names_only_known_ids():
    data = pick.load_data(ROOT, "Fedora", "44")
    known = set(data["alpi_catalog"]) | set(data["features_default"])
    named = [i for g in data["picker_groups"] for i in g["ids"]]
    assert len(named) == len(set(named))
    assert set(named) <= known
    assert set(data["picker_descriptions"]) <= known


def test_groups_keep_the_order_and_put_unknown_ids_last():
    data = {"picker_groups": [{"title": "Editors", "ids": ["vim", "nope"]},
                              {"title": "Empty", "ids": ["nope"]}]}
    grouped = pick.groups(data, PACKAGES)
    assert [(t, [c.id for c in m]) for t, m in grouped] == [("Editors", ["vim"]), ("Other", ["git", "gimp"])]


def test_changes_lists_additions_then_removals():
    assert pick.changes(PACKAGES, {"git", "gimp"}) == ["+ gimp: GIMP", "- vim: Vim"]


# --- Selection as differences from the defaults ---------------------------------------------

FEATURES = [pick.Choice("steam", "", True), pick.Choice("extra", "", False)]
PACKAGES = [pick.Choice("vim", "Vim", True), pick.Choice("git", "Git", True), pick.Choice("gimp", "GIMP", False)]
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
    result = pick.text_pick("T", [("G", PACKAGES)], {"vim", "git"}, read=lambda _: next(answers),
                            write=out.append)
    assert result == {"git"}
    assert "Unknown: nope. Nothing changed." in out
    assert "    - vim: Vim" in out  # the review, on accepting


def test_text_pick_numbers_run_across_groups():
    answers = iter(["3", ""])
    out = []
    grouped = [("A", PACKAGES[:2]), ("B", PACKAGES[2:])]
    result = pick.text_pick("T", grouped, {"vim", "git"}, read=lambda _: next(answers), write=out.append)
    assert result == {"vim", "git", "gimp"}
    assert "\n  B" in out


# --- whiptail interface (whiptail itself replaced by scripted answers) ----------------------


def scripted_whiptail(monkeypatch, answers):
    """Replaces whiptail: each call pops the next answer (None = Cancel/Back/No); records the
    calls' arguments."""
    feed, calls = iter(answers), []
    def fake(*args):
        calls.append(args)
        return next(feed)
    monkeypatch.setattr(pick, "_whiptail", fake)
    return calls


GROUPED = [("Editors", PACKAGES[:1]), ("Tools", PACKAGES[1:])]


def test_whiptail_opens_a_group_reviews_and_saves(monkeypatch):
    # Tools: git off, gimp on; review: Back; review again: Save
    calls = scripted_whiptail(monkeypatch, ["Tools", "gimp\n", "Review and save", None,
                                            "Review and save", ""])
    assert pick.whiptail_pick("T", GROUPED, {"vim", "git"}) == {"vim", "gimp"}
    menu = calls[0]
    assert "Editors" in menu and "1/1 selected" in menu and "1/2 selected" in menu
    assert "--default-item" not in menu
    assert calls[2][calls[2].index("--default-item") + 1] == "Tools"
    assert "2 changes from the defaults" in calls[2]
    assert "+ gimp: GIMP\n- git: Git" in calls[3][-3]


def test_whiptail_back_in_a_group_keeps_its_choice(monkeypatch):
    scripted_whiptail(monkeypatch, ["Editors", None, "Review and save", ""])
    assert pick.whiptail_pick("T", GROUPED, {"vim", "git"}) == {"vim", "git"}


def test_whiptail_cancel_in_the_menu_cancels(monkeypatch):
    scripted_whiptail(monkeypatch, ["Tools", "\n", None])
    assert pick.whiptail_pick("T", GROUPED, {"vim", "git"}) is None


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
    rc, sel = run_main(tmp_path, monkeypatch, "fedora", ["-steam -tmux +chkrootkit", ""])
    assert rc == 0
    assert sel == {"packages_selection_add": [], "packages_selection_skip": ["tmux"],
                   "features_selection": {"steam": False}}
    # Second run, on EL with KDE: Steam is not listed there, its saved veto stays
    rc, sel = run_main(tmp_path, monkeypatch, "el10", ["-ktorrent", ""], xdg="KDE")
    assert sel == {"packages_selection_add": [], "packages_selection_skip": ["tmux", "ktorrent"],
                   "features_selection": {"steam": False}}


def test_main_rejects_an_unsupported_distro(tmp_path, monkeypatch):
    rc, sel = run_main(tmp_path, monkeypatch, "debian", [])
    assert rc == 1 and sel is None

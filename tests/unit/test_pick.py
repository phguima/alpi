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
    rows = {c.id: (c.label, c.detail) for c in packages}
    # Not packaged for EL, installed from Flathub or upstream instead: listed, the source in the detail
    assert rows["google-roboto-fonts"] == ("Roboto font", "upstream roboto")
    assert rows["telegram"] == ("Telegram messaging", "flatpak org.telegram.desktop")
    assert rows["vim"] == ("Vim editor", "vim-enhanced")


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
    assert (packages[0].label, packages[0].detail) == ("gimp", "")


# --- zsh aliases ----------------------------------------------------------------------------


@pytest.mark.parametrize("distro, major, update", [
    ("Fedora", "44", "sudo dnf upgrade --refresh -y; dnf needs-restarting"),
    ("AlmaLinux", "10", "sudo dnf upgrade --refresh -y; dnf needs-restarting -r"),
])
def test_zsh_aliases_are_listed_with_their_commands_rendered(distro, major, update):
    data = pick.load_data(ROOT, distro, major)
    zsh = {c.id: c for c in pick.zsh_choices(data)}
    assert list(zsh)[-1] == "full-update" and all(c.default for c in zsh.values())
    assert zsh["full-update"].detail == ("flatpak update -y; command -v npm >/dev/null && sudo npm update -g; "
                                         "command -v claude >/dev/null && claude update; "
                                         "command -v agy >/dev/null && agy update; " + update)
    assert zsh["lls"].label == "Long listing, folders first (root too)"
    assert zsh["agycli"].label == "Antigravity CLI in ~/wks (needs antigravity_cli)"
    # the cedilla flag only with the workaround on, which the picker cannot know: off
    assert zsh["antigravity-ide"].detail == '"~/wks/tools/antigravity/antigravity"'
    assert zsh["nvidia-run"].detail == data["nvidia_prime_env"]
    assert not any("{" in c.detail or "<" in c.detail for c in zsh.values())


def test_a_name_the_picker_cannot_know_shows_as_a_placeholder():
    assert pick.show_command("{{ nope }}/x {{ 'a' | upper }}", {}) == "<nope>/x A"


@pytest.mark.parametrize("distro, major", [("Fedora", "44"), ("AlmaLinux", "10")])
def test_zsh_alias_names_clash_with_nothing_and_require_known_ids(distro, major):
    # The picker toggles packages, features and aliases by name in one list
    data = pick.load_data(ROOT, distro, major)
    known = set(data["alpi_catalog"]) | set(data["features_default"])
    definitions = {**data["zsh_aliases"], **data["zsh_aliases_os"]}
    assert not set(definitions) & known
    assert {d["requires"] for d in definitions.values() if "requires" in d} <= known
    assert all(d.get("description") and d.get("cmd") for d in definitions.values())


# --- Aliases follow what they need ---------------------------------------------------------

TOOLS = [pick.Choice("zsh", "Z shell", True), pick.Choice("claude_code", "Claude Code", True)]
ALIASES = [pick.Choice("lls", "", True, requires=("zsh",)),
           pick.Choice("claudecli", "", True, requires=("zsh", "claude_code")),
           pick.Choice("nvidia-run", "", True, requires=("zsh", "nvidia-driver"))]
DEPS = [("Tools", TOOLS), ("Aliases", ALIASES)]


def shown_ids(grouped, checked):
    return {g: [c.id for c in m] for g, m in pick.visible(grouped, checked)}


def test_an_alias_is_hidden_while_its_program_is_unchecked():
    assert shown_ids(DEPS, {"zsh", "claude_code"})["Aliases"] == ["lls", "claudecli", "nvidia-run"]
    # nvidia-driver is not listed (detection decides): it hides nothing
    assert shown_ids(DEPS, {"zsh"})["Aliases"] == ["lls", "nvidia-run"]


def test_every_alias_and_their_group_go_without_zsh():
    assert shown_ids(DEPS, {"claude_code"}) == {"Tools": ["zsh", "claude_code"]}


def test_the_repository_aliases_need_zsh_and_their_requirement():
    zsh = {c.id: c for c in pick.zsh_choices(pick.load_data(ROOT, "Fedora", "44"))}
    assert zsh["lls"].requires == ("zsh",)
    assert zsh["agycli"].requires == ("zsh", "antigravity_cli")


def test_text_pick_hides_the_alias_lists_again_and_keeps_its_check():
    answers = iter(["-claude_code", "claudecli", "+claude_code", ""])
    out = []
    result = pick.text_pick("T", DEPS, {"zsh", "claude_code", "lls", "claudecli", "nvidia-run"},
                            read=lambda _: next(answers), write=out.append)
    # hidden: cannot be toggled; the list is shown again (the numbers changed) when it goes and comes back
    assert "Unknown: claudecli. Nothing changed." in out
    assert sum(line.startswith("  4 [x] claudecli") for line in out) == 2
    assert sum(line == "\n  Aliases" for line in out) == 3
    assert result == {"zsh", "claude_code", "lls", "claudecli", "nvidia-run"}


def test_whiptail_menu_counts_and_opens_only_what_is_shown(monkeypatch):
    # Tools: claude_code off; the aliases menu entry then counts 2, its checklist lists 2
    calls = scripted_whiptail(monkeypatch, ["Tools", "zsh\n", "Aliases", "lls\n", None])
    checked = {"zsh", "claude_code", "lls", "claudecli", "nvidia-run"}
    assert pick.whiptail_pick("T", DEPS, checked) is None
    assert "3/3 selected" in calls[0] and "2/2 selected" in calls[2]
    assert "claudecli" not in calls[3] and "nvidia-run" in calls[3]


def test_whiptail_saves_a_hidden_alias_as_it_was(monkeypatch):
    scripted_whiptail(monkeypatch, ["Tools", "zsh\n", "Review and save", ""])
    checked = {"zsh", "claude_code", "lls", "claudecli", "nvidia-run"}
    assert pick.whiptail_pick("T", DEPS, checked) == checked - {"claude_code"}


# --- Rows -----------------------------------------------------------------------------------


def test_rows_align_the_labels_and_put_the_detail_after():
    items = [pick.Choice("a", "Short", True, "pkg-a"), pick.Choice("bb", "A longer label", True)]
    assert pick.rows(items, 40) == ["Short           pkg-a", "A longer label"]


def test_rows_cut_the_detail_first_and_pad_to_the_width():
    items = [pick.Choice("id", "Label", True, "x" * 50)]
    assert pick.rows(items, 30) == ["Label  " + "x" * 19 + "…"]
    assert pick.rows([pick.Choice("id", "Label", True)], 20, pad=True) == ["Label".ljust(20)]


def test_rows_keep_24_columns_for_the_detail_and_half_the_row_at_least():
    long = pick.Choice("id", "L" * 80, True, "detail")
    assert len(pick.rows([long], 103)[0].split("  ")[0]) == 100 - 26
    assert len(pick.rows([long], 43)[0].split("  ")[0]) == 20


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


ZSH = [pick.Choice("lls", "", True), pick.Choice("agycli", "", True)]


def test_selection_stores_only_differences():
    sel, dropped = pick.selection(FEATURES, PACKAGES, {"extra"}, {"git", "gimp"}, {}, CATALOG,
                                  zsh=ZSH, zsh_on={"agycli"})
    assert sel == {"packages_selection_add": ["gimp"], "packages_selection_skip": ["vim"],
                   "features_selection": {"steam": False, "extra": True},
                   "zsh_aliases_selection": {"lls": False}}
    assert dropped == []


def test_unchanged_defaults_give_an_empty_selection():
    sel, _ = pick.selection(FEATURES, PACKAGES, {"steam"}, {"vim", "git"}, {}, CATALOG, zsh=ZSH,
                            zsh_on={"lls", "agycli"})
    assert sel == {"packages_selection_add": [], "packages_selection_skip": [], "features_selection": {},
                   "zsh_aliases_selection": {}}


def test_saved_entries_for_ids_not_listed_are_kept_and_unknown_ones_dropped():
    saved = {"packages_selection_skip": ["ktorrent", "vim", "gone"], "features_selection": {"other": False},
             "zsh_aliases_selection": {"lls": False, "elsewhere": False}}
    sel, dropped = pick.selection(FEATURES, PACKAGES, {"steam"}, {"vim", "git"}, saved, CATALOG,
                                  zsh=ZSH, zsh_on={"lls", "agycli"})
    # vim is listed and checked now: no longer skipped; ktorrent (another desktop) is kept
    assert sel["packages_selection_skip"] == ["ktorrent"]
    assert sel["features_selection"] == {"other": False}
    # lls is checked again; an alias of another distro's zsh_aliases_os is kept
    assert sel["zsh_aliases_selection"] == {"elsewhere": False}
    assert dropped == ["gone"]


def test_initial_applies_a_saved_selection_through_aliases():
    saved = {"packages_selection_skip": ["vim-old"], "packages_selection_add": ["gimp"],
             "features_selection": {"steam": False}, "zsh_aliases_selection": {"lls": False}}
    feats_on, pkgs_on, zsh_on = pick.initial(FEATURES, PACKAGES, saved, {"vim-old": "vim"}, ZSH)
    assert feats_on == set()
    assert pkgs_on == {"git", "gimp"}
    assert zsh_on == {"agycli"}


def test_round_trip_through_the_file(tmp_path):
    sel, _ = pick.selection(FEATURES, PACKAGES, set(), {"vim"}, {}, CATALOG, zsh=ZSH, zsh_on={"lls"})
    pick.write_selection(tmp_path / "h" / "selection.yml", sel)
    text = (tmp_path / "h" / "selection.yml").read_text()
    assert text.startswith("---\n# Written by pick.py")
    assert pick.initial(FEATURES, PACKAGES, yaml.safe_load(text), zsh=ZSH) == (set(), {"vim"}, {"lls"})


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
    # the list as tall as its entries (two groups and the review), not the terminal
    assert menu[menu.index(pick.WIDTH) + 1] == "3"
    assert calls[2][calls[2].index("--default-item") + 1] == "Tools"
    assert "2 changes from the defaults" in calls[2]
    assert "+ gimp: GIMP\n- git: Git" in calls[3][-3]


def test_whiptail_rows_fill_the_box(monkeypatch):
    calls = scripted_whiptail(monkeypatch, ["Tools", None, None])
    monkeypatch.setattr(pick, "_sizes", lambda: (30, 100, 22))
    pick.whiptail_pick("T", GROUPED, {"vim", "git"})
    checklist = calls[1]
    rows = checklist[checklist.index(pick.LIST) + 1:]
    assert rows[0] == "git" and rows[2] == "ON" and rows[3] == "gimp"
    assert rows[1].startswith("Git ") and len(rows[1]) == 100 - 13 - len("gimp") - 1


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
    rc, sel = run_main(tmp_path, monkeypatch, "fedora", ["-steam -tmux +chkrootkit -lls", ""])
    assert rc == 0
    assert sel == {"packages_selection_add": [], "packages_selection_skip": ["tmux"],
                   "features_selection": {"steam": False}, "zsh_aliases_selection": {"lls": False}}
    # Second run, on EL with KDE: Steam is not listed there, its saved veto stays
    rc, sel = run_main(tmp_path, monkeypatch, "el10", ["-ktorrent", ""], xdg="KDE")
    assert sel == {"packages_selection_add": [], "packages_selection_skip": ["tmux", "ktorrent"],
                   "features_selection": {"steam": False}, "zsh_aliases_selection": {"lls": False}}


def test_load_data_layers_the_family_before_the_distro(tmp_path):
    gv = tmp_path / "group_vars"
    files = {
        "all/catalog.yml": "{}", "all/packages.yml": "{}", "all/features.yml": "{}",
        "all/picker.yml": "{}", "all/zsh.yml": "{}", "all/ai_tools.yml": "{}", "all/desktop.yml": "{}",
        "family_RedHat/main.yml": "family_key: rpm\nlayer: family\n",
        "family_Debian/main.yml": "debian_key: deb\n",
        "os_Fedora/main.yml": "layer: distro\n",
        "os_Fedora_44/main.yml": "major_key: 44\n",
    }
    for name, text in files.items():
        (gv / name).parent.mkdir(parents=True, exist_ok=True)
        (gv / name).write_text(text)
    data = pick.load_data(tmp_path, "Fedora", "44")
    assert data == {"family_key": "rpm", "layer": "distro", "major_key": 44}


@pytest.mark.parametrize("distro,major", [("Fedora", "44"), ("AlmaLinux", "10")])
def test_rpm_distros_try_the_rpm_key_before_all(distro, major):
    assert pick.load_data(ROOT, distro, major)["alpi_catalog_keys"][-2:] == ["rpm", "all"]


def test_every_distro_has_a_family():
    assert set(pick.DISTROS.values()) <= set(pick.FAMILIES)


def test_main_rejects_an_unsupported_distro(tmp_path, monkeypatch):
    rc, sel = run_main(tmp_path, monkeypatch, "debian", [])
    assert rc == 1 and sel is None

#!/usr/bin/env python3
"""ALPI package picker: choose the features and packages for this machine.

Lists only what the running distro can install (catalog entries marked ~ are hidden, so are the
other desktop's packages and features whose packages are all unavailable), in groups by purpose
(group_vars/all/picker.yml), and the zsh aliases (group_vars/all/zsh.yml) as a last group: a menu of
groups, each opened as a checklist (description, then what gets installed, or the alias's
command), then a review of the changes before saving. The repository defaults start checked. The
choice is saved to host_vars/127.0.0.1/selection.yml as differences from the defaults
(packages_selection_add/_skip, features_selection, zsh_aliases_selection), so defaults added to
the repository later still arrive with git pull. Hardware features (NVIDIA, ASUS…) follow
detection and are not listed; veto them in custom.yml.

./bootstrap.sh runs it; run it again at any time to change the choice. ALPI_PICKER=text (or
--ui text) uses plain prompts instead of whiptail.
"""

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
# /etc/os-release ID -> Ansible's distribution name (group_vars/os_<name>). The playbook's support
# matrix (group_vars/all/support.yml) is the authoritative check.
DISTROS = {"fedora": "Fedora", "almalinux": "AlmaLinux"}
# Ansible's os_family per distribution (group_vars/family_<family>)
FAMILIES = {"Fedora": "RedHat", "AlmaLinux": "RedHat", "Debian": "Debian", "Ubuntu": "Debian"}
# The zsh aliases' group, last in the menu (only for zsh: roles/zsh writes them)
ZSH_GROUP = "Shell aliases (zsh)"
HEADER = """---
# Written by pick.py (./bootstrap.sh runs it; run ./pick.py again to change the choice). Only the
# differences from the repository defaults, so new defaults still arrive with git pull.
# Hand-written settings go in custom.yml next to this file, which is applied after this one.
"""


def _load_filters(root):
    spec = importlib.util.spec_from_file_location("alpi_filters", root / "filter_plugins" / "alpi.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass
class Choice:
    id: str
    label: str
    default: bool
    detail: str = ""  # what it installs, or the alias's command
    requires: tuple = ()  # ids it needs: hidden while one of them is listed and unchecked


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f) or {}


def os_release(path="/etc/os-release"):
    out = {}
    with open(path) as f:
        for line in f:
            key, sep, value = line.strip().partition("=")
            if sep:
                out[key] = value.strip("\"'")
    return out


def load_data(root, distro, major):
    """The repository data the playbook would use on this distro."""
    gv = root / "group_vars"
    data = {}
    # zsh: the aliases; ai_tools and desktop: values their commands show (antigravity_ide_dir…)
    for name in ("catalog", "packages", "features", "picker", "zsh", "ai_tools", "desktop"):
        data.update(load_yaml(gv / "all" / f"{name}.yml"))
    # Same layering as group_by in env_setup: family_<os_family>, os_<distro>, os_<distro>_<major>
    for group in (f"family_{FAMILIES[distro]}", f"os_{distro}", f"os_{distro}_{major}"):
        for path in sorted((gv / group).glob("*.yml")) if (gv / group).is_dir() else []:
            data.update(load_yaml(path))
    return data


def desktops(xdg):
    """Same rule as env_setup's is_gnome/is_kde."""
    xdg = (xdg or "").upper()
    return {name for name, hit in (("gnome", "GNOME" in xdg), ("kde", "KDE" in xdg or "PLASMA" in xdg)) if hit}


def _names(res):
    return ", ".join(res["native"] + [f"flatpak {n}" for n in res["flatpak"]]
                     + [f"pipx {n}" for n in res.get("pipx", [])]
                     + [f"upstream {n}" for n in res.get("upstream", [])])


def _choice(cid, res, descriptions, default):
    """The id's description, and the names it installs as the detail; the names as the label
    when there is no description."""
    if cid not in descriptions:
        return Choice(cid, _names(res), default)
    return Choice(cid, descriptions[cid], default, _names(res))


def choices(data, des, filters):
    """(features, packages) the user can choose on this distro, as Choice lists."""
    resolve = lambda ids: filters.alpi_resolve(ids, data["alpi_catalog"], data["alpi_catalog_keys"],
                                               data.get("alpi_catalog_aliases"))
    feature_packages = data.get("feature_packages") or {}
    hardware = set(data.get("alpi_hardware_features") or [])
    descriptions = data.get("picker_descriptions") or {}

    features = []
    for name, value in (data.get("features_default") or {}).items():
        if name in hardware:
            continue
        res = resolve(feature_packages.get(name) or [])
        if feature_packages.get(name) and not (res["native"] or res["flatpak"] or res.get("pipx")
                                               or res.get("upstream")):
            continue  # nothing to install here (Steam on EL)
        features.append(_choice(name, res, descriptions, bool(value)))

    desktop_lists = {"kde": data.get("packages_kde") or [], "gnome": data.get("packages_gnome") or []}
    defaults = list(data.get("packages_base") or []) + list(data.get("packages_os") or [])
    for de in sorted(des):
        defaults += desktop_lists[de]
    hidden = {i for de, ids in desktop_lists.items() if de not in des for i in ids} - set(defaults)
    owned = {i for ids in feature_packages.values() for i in ids or []}

    packages = []
    for pid in data["alpi_catalog"]:
        if pid in owned or pid in hidden:
            continue
        res = resolve([pid])
        if res["unavailable"] or res["missing"]:
            continue
        packages.append(_choice(pid, res, descriptions, pid in defaults))
    return features, packages


def show_command(cmd, data):
    """An alias's command as the playbook would write it, for the picker: the templates rendered
    with the repository's values (the user's home as ~); a name it cannot know shows as <name>.
    Unrendered when Jinja is missing (it comes with ansible-core)."""
    try:
        import jinja2
    except ImportError:
        return cmd

    class Placeholder(jinja2.Undefined):
        def __str__(self):
            return f"<{self._undefined_name}>"

    env, context = jinja2.Environment(undefined=Placeholder), {**data, "user_home": "~"}
    for _ in range(5):  # a value may hold templates of its own (zsh_full_update_tools)
        if "{{" not in cmd and "{%" not in cmd:
            break
        try:
            cmd = env.from_string(cmd).render(context)
        except jinja2.TemplateError:
            break
    return cmd


def zsh_choices(data):
    """The zsh aliases (zsh_aliases + the distro's zsh_aliases_os), all on by default. Each needs
    zsh, and its requires (the playbook leaves it out without them)."""
    definitions = {**(data.get("zsh_aliases") or {}), **(data.get("zsh_aliases_os") or {})}
    out = []
    for name, d in definitions.items():
        notes = (["root too"] if d.get("root") else []) + ([f"needs {d['requires']}"] if d.get("requires") else [])
        label = d.get("description", name) + (f" ({', '.join(notes)})" if notes else "")
        requires = ("zsh",) + ((d["requires"],) if d.get("requires") else ())
        out.append(Choice(name, label, True, show_command(str(d["cmd"]), data), requires))
    return out


def rows(items, width, pad=False):
    """Each item's text in a list width columns wide after its id column: the label padded to a
    shared column, then the detail, cut to fit (pad: filled with spaces to the full width). The label comes first: it gets its full width
    while the detail keeps 24 columns, and at least half the row otherwise."""
    if not items:
        return []
    avail = max(width - max(len(c.id) for c in items) - 1, 20)
    label_w = min(max(len(c.label) for c in items), max(avail - 26, avail // 2))
    out = []
    for c in items:
        label = c.label if len(c.label) <= label_w else c.label[:label_w - 1] + "…"
        text = f"{label:<{label_w}}  {c.detail}".rstrip() if c.detail else label
        text = text if len(text) <= avail else text[:avail - 1] + "…"
        out.append(f"{text:<{avail}}" if pad else text)
    return out


def visible(grouped, checked):
    """The groups as shown now: an item is hidden while an id it requires is listed and unchecked
    (an alias whose program is off; all aliases without zsh), and so is a group left empty. Its
    own check stays, so it comes back as it was. An id the picker does not list (nvidia-driver,
    from detection) hides nothing: the playbook decides."""
    listed = {c.id for _, members in grouped for c in members}
    shown = [(g, [c for c in members if all(r in checked or r not in listed for r in c.requires)])
             for g, members in grouped]
    return [(g, members) for g, members in shown if members]


def groups(data, items):
    """[(title, choices)] in picker.yml's order, empty groups left out; ids no group names go
    last, under "Other"."""
    by_id = {c.id: c for c in items}
    out, placed = [], set()
    for group in data.get("picker_groups") or []:
        members = [by_id[i] for i in group.get("ids") or [] if i in by_id and i not in placed]
        placed.update(c.id for c in members)
        if members:
            out.append((group["title"], members))
    rest = [c for c in items if c.id not in placed]
    if rest:
        out.append(("Other", rest))
    return out


def changes(items, checked):
    """Lines describing the choice's differences from the defaults, for the review."""
    return ([f"+ {c.id}: {c.label}" for c in items if c.id in checked and not c.default]
            + [f"- {c.id}: {c.label}" for c in items if c.default and c.id not in checked])


def initial(features, packages, saved, aliases=None, zsh=()):
    """Checked ids for the pickers: the defaults with a saved selection applied. Returns
    (features, packages, zsh aliases)."""
    aliases = aliases or {}
    add = {aliases.get(i, i) for i in saved.get("packages_selection_add") or []}
    skip = {aliases.get(i, i) for i in saved.get("packages_selection_skip") or []}
    pkgs_on = {c.id for c in packages if (c.default or c.id in add) and c.id not in skip}
    on = lambda items, key: {c.id for c in items if bool((saved.get(key) or {}).get(c.id, c.default))}
    return on(features, "features_selection"), pkgs_on, on(zsh, "zsh_aliases_selection")


def selection(features, packages, feats_on, pkgs_on, saved, catalog, aliases=None, zsh=(),
              zsh_on=frozenset()):
    """The differences from the defaults, plus saved entries for ids not listed this time
    (another desktop's packages picked from that desktop), so a run elsewhere keeps them.
    Returns (selection, dropped ids no longer in the catalog)."""
    aliases = aliases or {}
    listed = {c.id for c in packages}
    out = {"packages_selection_add": [c.id for c in packages if c.id in pkgs_on and not c.default],
           "packages_selection_skip": [c.id for c in packages if c.default and c.id not in pkgs_on]}
    dropped = []
    for key in ("packages_selection_add", "packages_selection_skip"):
        for raw in saved.get(key) or []:
            pid = aliases.get(raw, raw)
            if pid not in catalog:
                dropped.append(raw)
            elif pid not in listed and pid not in out[key]:
                out[key].append(pid)
    for key, items, on in (("features_selection", features, feats_on), ("zsh_aliases_selection", zsh, zsh_on)):
        out[key] = {c.id: c.id in on for c in items if (c.id in on) != c.default}
        for name, value in (saved.get(key) or {}).items():
            if name not in {c.id for c in items}:
                out[key].setdefault(name, value)
    return out, dropped


def write_selection(path, sel):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(HEADER)
        yaml.safe_dump(sel, f, sort_keys=False, default_flow_style=False)


def parse_toggles(line, items, checked):
    """Apply a line of toggles: 'id' or a number flips it, '+id' checks, '-id' unchecks.
    Returns (new checked set, unknown tokens); nothing is applied when a token is unknown."""
    ids = [c.id for c in items]
    new, unknown = set(checked), []
    for token in line.split():
        op, name = (token[0], token[1:]) if token[0] in "+-" else ("", token)
        if name.isdigit() and 1 <= int(name) <= len(ids):
            name = ids[int(name) - 1]
        if name not in ids:
            unknown.append(token)
        elif op == "+" or (not op and name not in new):
            new.add(name)
        else:
            new.discard(name)
    return (set(checked), unknown) if unknown else (new, [])


def text_pick(title, grouped, checked, read=None, write=print):
    """Every group in one numbered list; toggles by id or number until an empty line."""
    read = read or input  # looked up at call time, so tests can replace it
    items = [c for _, members in grouped for c in members]
    shown = lambda: [c for _, members in visible(grouped, checked) for c in members]
    def show():
        width = shutil.get_terminal_size((100, 30)).columns - 9  # after "nnn [x] "
        write(f"\n{title}")
        n = 0
        for group, members in visible(grouped, checked):  # each aligned on its own, as in whiptail
            write(f"\n  {group}")
            id_w = max(len(c.id) for c in members)
            for c, text in zip(members, rows(members, width)):
                n += 1
                write(f"{n:3} [{'x' if c.id in checked else ' '}] {c.id:<{id_w}} {text}")
    show()
    while True:
        try:
            line = read("Toggle ids or numbers (+id on, -id off, ? list, Enter to accept): ")
        except EOFError:
            return checked
        if not line.strip():
            for change in changes(items, checked):
                write(f"    {change}")
            return checked
        if line.strip() == "?":
            show()
            continue
        before = shown()
        new, unknown = parse_toggles(line, before, checked)
        if unknown:
            write(f"Unknown: {' '.join(unknown)}. Nothing changed.")
            continue
        for c in items:
            if (c.id in new) != (c.id in checked):
                write(f"    {c.id}: {'on' if c.id in new else 'off'}")
        checked = new
        if shown() != before:  # items appeared or went: the numbers changed
            show()


# Stand-ins for whiptail's box height, width and list height, filled in from the terminal's size
HEIGHT, WIDTH, LIST = object(), object(), object()


def _sizes():
    """whiptail's box height, width and list height for this terminal."""
    size = shutil.get_terminal_size((100, 30))
    height = max(size.lines - 2, 15)
    return height, max(min(size.columns - 4, 160), 60), height - 8


def _whiptail(*args):
    """whiptail's answer (stderr), or None when cancelled (Esc, Cancel or No)."""
    height, width, list_height = _sizes()
    sizes = {HEIGHT: str(height), WIDTH: str(width), LIST: str(list_height)}
    cmd = ["whiptail", "--title", "ALPI"] + [sizes.get(a, a) for a in args]
    r = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
    return r.stderr if r.returncode == 0 else None


def whiptail_checklist(title, items, checked):
    """The group's checked ids, or None when cancelled."""
    args = ["--separate-output", "--ok-button", "Done", "--cancel-button", "Back", "--checklist",
            f"{title}\nSpace toggles, Enter goes back to the groups.", HEIGHT, WIDTH, LIST]
    # The list is as wide as its longest row: the rows are padded to fill the box (borders, the
    # "[*] " column and the gap after the ids take about 13 columns)
    for c, text in zip(items, rows(items, _sizes()[1] - 13, pad=True)):
        args += [c.id, text, "ON" if c.id in checked else "OFF"]
    answer = _whiptail(*args)
    return None if answer is None else set(answer.split())


def whiptail_pick(title, grouped, checked):
    """Menu of groups, each a checklist, then a review of the changes. Checked ids, or None when
    cancelled."""
    save, current = "Review and save", None
    items = [c for _, members in grouped for c in members]
    while True:
        shown = visible(grouped, checked)
        args = ["--ok-button", "Open", "--cancel-button", "Cancel"]
        if current in dict(shown):
            args += ["--default-item", current]
        # The list as tall as its entries: a taller one hides the text's second line
        args += ["--menu", f"{title}\nOpen a group to change it. Defaults are checked.", HEIGHT, WIDTH,
                 str(len(shown) + 1)]
        for group, members in shown:
            args += [group, f"{sum(c.id in checked for c in members)}/{len(members)} selected"]
        n = len(changes(items, checked))
        args += [save, f"{n} change{'' if n == 1 else 's'} from the defaults"]
        current = _whiptail(*args)
        if current is None:
            return None
        if current == save:
            lines = changes(items, checked) or ["No changes: the defaults."]
            # A scroll box takes the keyboard focus (Tab to reach Save): only when it must scroll
            scroll = ["--scrolltext"] if len(lines) > shutil.get_terminal_size((100, 30)).lines - 12 else []
            if _whiptail(*scroll, "--yes-button", "Save", "--no-button", "Back", "--yesno",
                         "Changes from the defaults:\n\n" + "\n".join(lines), HEIGHT, WIDTH) is not None:
                return checked
            continue
        members = dict(shown)[current]
        picked = whiptail_checklist(f"{title}: {current}", members, checked)
        if picked is not None:
            checked = (checked - {c.id for c in members}) | picked


def main(argv=None):
    ap = argparse.ArgumentParser(description="Choose the features and packages for this machine.")
    ap.add_argument("--ui", choices=["auto", "whiptail", "text"], default=os.environ.get("ALPI_PICKER", "auto"))
    ap.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    ap.add_argument("--os-release", default="/etc/os-release", help=argparse.SUPPRESS)
    ap.add_argument("--output", type=Path, help="default: host_vars/127.0.0.1/selection.yml")
    args = ap.parse_args(argv)
    output = args.output or args.root / "host_vars" / "127.0.0.1" / "selection.yml"

    rel = os_release(args.os_release)
    distro = DISTROS.get(rel.get("ID", ""))
    if not distro:
        print(f"ERROR: {rel.get('PRETTY_NAME', 'this distro')} is not supported (yet).", file=sys.stderr)
        return 1
    data = load_data(args.root, distro, rel.get("VERSION_ID", "").split(".")[0])
    des = desktops(os.environ.get("XDG_CURRENT_DESKTOP"))
    features, packages = choices(data, des, _load_filters(args.root))
    zsh = zsh_choices(data)
    saved = load_yaml(output) if output.exists() else {}
    aliases = data.get("alpi_catalog_aliases") or {}
    feats_on, pkgs_on, zsh_on = initial(features, packages, saved, aliases, zsh)

    ui = args.ui
    if ui == "auto":
        ui = "whiptail" if shutil.which("whiptail") and sys.stdin.isatty() else "text"
    pick = whiptail_pick if ui == "whiptail" else text_pick
    where = f"{rel.get('PRETTY_NAME', distro)}, desktop: {'/'.join(sorted(des)).upper() or 'none detected'}"
    print(f"==> Package picker ({where}). Hardware features follow detection; veto them in custom.yml.")
    grouped = groups(data, features + packages) + ([(ZSH_GROUP, zsh)] if zsh else [])
    checked = pick(where, grouped, feats_on | pkgs_on | zsh_on)
    if checked is None:
        print(f"Cancelled: {output} left unchanged.")
        return 0
    feats_on, pkgs_on, zsh_on = ({c.id for c in items if c.id in checked} for items in (features, packages, zsh))

    sel, dropped = selection(features, packages, feats_on, pkgs_on, saved, data["alpi_catalog"], aliases,
                             zsh, zsh_on)
    for raw in dropped:
        print(f"WARNING: '{raw}' is no longer in the catalog; dropped from the selection.")
    write_selection(output, sel)
    print(f"Selection saved to {output}: {len(sel['packages_selection_add'])} added, "
          f"{len(sel['packages_selection_skip'])} skipped, features changed: "
          f"{', '.join(f'{k}={v}' for k, v in sel['features_selection'].items()) or 'none'}; zsh aliases "
          f"changed: {', '.join(f'{k}={v}' for k, v in sel['zsh_aliases_selection'].items()) or 'none'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""ALPI package picker: choose the features and packages for this machine.

Lists only what the running distro can install (catalog entries marked ~ are hidden, so are the
other desktop's packages and features whose packages are all unavailable). The repository
defaults start checked. The choice is saved to host_vars/127.0.0.1/selection.yml as differences
from the defaults (packages_selection_add/_skip, features_selection), so defaults added to the
repository later still arrive with git pull. Hardware features (NVIDIA, ASUS…) follow detection
and are not listed; veto them in custom.yml.

./bootstrap.sh runs it; run it again at any time to change the choice. ALPI_PICKER=text (or
--ui text) uses plain prompts instead of whiptail.
"""

import argparse
import importlib.util
import os
import re
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


def catalog_sections(path):
    """Catalog id -> section title, from the '# --- Title ---' comments in catalog.yml."""
    sections, current = {}, ""
    for line in Path(path).read_text().splitlines():
        m = re.match(r"\s*# --- (.+?) ---", line)
        if m:
            current = m.group(1)
            continue
        m = re.match(r"  ([A-Za-z0-9][\w.+-]*):", line)
        if m:
            sections[m.group(1)] = current
    return sections


def load_data(root, distro, major):
    """The repository data the playbook would use on this distro."""
    gv = root / "group_vars"
    data = {}
    for name in ("catalog", "packages", "features"):
        data.update(load_yaml(gv / "all" / f"{name}.yml"))
    # Same layering as group_by in env_setup: os_<distro>, then os_<distro>_<major>
    for group in (f"os_{distro}", f"os_{distro}_{major}"):
        for path in sorted((gv / group).glob("*.yml")) if (gv / group).is_dir() else []:
            data.update(load_yaml(path))
    data["sections"] = catalog_sections(gv / "all" / "catalog.yml")
    return data


def desktops(xdg):
    """Same rule as env_setup's is_gnome/is_kde."""
    xdg = (xdg or "").upper()
    return {name for name, hit in (("gnome", "GNOME" in xdg), ("kde", "KDE" in xdg or "PLASMA" in xdg)) if hit}


def _names(res):
    return ", ".join(res["native"] + [f"flatpak {n}" for n in res["flatpak"]]
                     + [f"pipx {n}" for n in res.get("pipx", [])]
                     + [f"upstream {n}" for n in res.get("upstream", [])])


def choices(data, des, filters):
    """(features, packages) the user can choose on this distro, as Choice lists."""
    resolve = lambda ids: filters.alpi_resolve(ids, data["alpi_catalog"], data["alpi_catalog_keys"],
                                               data.get("alpi_catalog_aliases"))
    feature_packages = data.get("feature_packages") or {}
    hardware = set(data.get("alpi_hardware_features") or [])
    descriptions = data.get("feature_descriptions") or {}

    features = []
    for name, value in (data.get("features_default") or {}).items():
        if name in hardware:
            continue
        res = resolve(feature_packages.get(name) or [])
        if feature_packages.get(name) and not (res["native"] or res["flatpak"] or res.get("pipx")
                                               or res.get("upstream")):
            continue  # nothing to install here (Steam on EL)
        features.append(Choice(name, descriptions.get(name) or _names(res), bool(value)))

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
        section = data["sections"].get(pid, "")
        packages.append(Choice(pid, f"{section}: {_names(res)}" if section else _names(res), pid in defaults))
    return features, packages


def initial(features, packages, saved, aliases=None):
    """Checked ids for the pickers: the defaults with a saved selection applied."""
    aliases = aliases or {}
    add = {aliases.get(i, i) for i in saved.get("packages_selection_add") or []}
    skip = {aliases.get(i, i) for i in saved.get("packages_selection_skip") or []}
    feats = saved.get("features_selection") or {}
    pkgs_on = {c.id for c in packages if (c.default or c.id in add) and c.id not in skip}
    feats_on = {c.id for c in features if bool(feats.get(c.id, c.default))}
    return feats_on, pkgs_on


def selection(features, packages, feats_on, pkgs_on, saved, catalog, aliases=None):
    """The differences from the defaults, plus saved entries for ids not listed this time
    (another desktop's packages picked from that desktop), so a run elsewhere keeps them.
    Returns (selection, dropped ids no longer in the catalog)."""
    aliases = aliases or {}
    listed = {c.id for c in packages}
    feats_listed = {c.id for c in features}
    out = {"packages_selection_add": [c.id for c in packages if c.id in pkgs_on and not c.default],
           "packages_selection_skip": [c.id for c in packages if c.default and c.id not in pkgs_on],
           "features_selection": {c.id: c.id in feats_on for c in features if (c.id in feats_on) != c.default}}
    dropped = []
    for key in ("packages_selection_add", "packages_selection_skip"):
        for raw in saved.get(key) or []:
            pid = aliases.get(raw, raw)
            if pid not in catalog:
                dropped.append(raw)
            elif pid not in listed and pid not in out[key]:
                out[key].append(pid)
    for name, value in (saved.get("features_selection") or {}).items():
        if name not in feats_listed:
            out["features_selection"].setdefault(name, value)
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


def text_pick(title, items, checked, read=None, write=print):
    read = read or input  # looked up at call time, so tests can replace it
    def show():
        write(f"\n{title}")
        for n, c in enumerate(items, 1):
            write(f"{n:3} [{'x' if c.id in checked else ' '}] {c.id:<26} {c.label}")
    show()
    while True:
        try:
            line = read("Toggle ids or numbers (+id on, -id off, ? list, Enter to accept): ")
        except EOFError:
            return checked
        if not line.strip():
            return checked
        if line.strip() == "?":
            show()
            continue
        new, unknown = parse_toggles(line, items, checked)
        if unknown:
            write(f"Unknown: {' '.join(unknown)}. Nothing changed.")
            continue
        for c in items:
            if (c.id in new) != (c.id in checked):
                write(f"    {c.id}: {'on' if c.id in new else 'off'}")
        checked = new


def whiptail_pick(title, items, checked):
    """Checked ids, or None when cancelled."""
    size = shutil.get_terminal_size((100, 30))
    height = max(size.lines - 2, 15)
    cmd = ["whiptail", "--title", "ALPI", "--separate-output", "--checklist",
           f"{title}\nSpace toggles, Enter accepts.", str(height), str(min(size.columns - 4, 110)),
           str(height - 8)]
    for c in items:
        cmd += [c.id, c.label[:70], "ON" if c.id in checked else "OFF"]
    r = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
    return set(r.stderr.split()) if r.returncode == 0 else None


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
    saved = load_yaml(output) if output.exists() else {}
    aliases = data.get("alpi_catalog_aliases") or {}
    feats_on, pkgs_on = initial(features, packages, saved, aliases)

    ui = args.ui
    if ui == "auto":
        ui = "whiptail" if shutil.which("whiptail") and sys.stdin.isatty() else "text"
    pick = whiptail_pick if ui == "whiptail" else text_pick
    where = f"{rel.get('PRETTY_NAME', distro)}, desktop: {'/'.join(sorted(des)).upper() or 'none detected'}"
    print(f"==> Package picker ({where}). Hardware features follow detection; veto them in custom.yml.")
    feats_on = pick(f"Features ({where})", features, feats_on)
    if feats_on is not None:
        pkgs_on = pick(f"Packages ({where})", packages, pkgs_on)
    if feats_on is None or pkgs_on is None:
        print(f"Cancelled: {output} left unchanged.")
        return 0

    sel, dropped = selection(features, packages, feats_on, pkgs_on, saved, data["alpi_catalog"], aliases)
    for raw in dropped:
        print(f"WARNING: '{raw}' is no longer in the catalog; dropped from the selection.")
    write_selection(output, sel)
    print(f"Selection saved to {output}: {len(sel['packages_selection_add'])} added, "
          f"{len(sel['packages_selection_skip'])} skipped, features changed: "
          f"{', '.join(f'{k}={v}' for k, v in sel['features_selection'].items()) or 'none'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

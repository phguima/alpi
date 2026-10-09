# ALPI filters: resolve logical package ids through the catalog (see PROPOSAL.md, "Customization").

import re

# Raw names bypass the catalog: "pkg:<native name>", "flatpak:<app id>" or "pipx:<PyPI spec>".
RAW_PREFIXES = {"pkg": "native", "flatpak": "flatpak", "pipx": "pipx"}


def alpi_resolve(ids, catalog, keys, aliases=None):
    """Resolve logical ids for the current distro.

    keys: catalog keys to try, most specific first (e.g. ["el10", "el", "all"]).
    Returns a dict:
      native / flatpak / pipx: names to install with the package manager / Flatpak / pipx (pipx
                   values are PyPI specs, extras included: "markitdown[all]");
      unknown:     ids missing from the catalog (user or repo error);
      missing:     ids in the catalog with no entry for any of the keys (catalog bug);
      unavailable: ids marked ~ (null) for this distro (skipped with a warning);
      repos:       repository ids that the resolved native packages need (an entry's 'repo'
                   key, a string or a list; Flatpak values need no repository). A per-distro
                   value {native: <name or list>, repo: <id or list>} names its own
                   repository instead, for a source that only one distro needs;
      swap:        native names of entries with 'swap: true', which replace a conflicting
                   package (ffmpeg-free -> ffmpeg) and are installed first with allowerasing.
                   They are in 'native' too, so name checks and verification cover them.
    """
    aliases = aliases or {}
    out = {"native": [], "flatpak": [], "pipx": [], "unknown": [], "missing": [], "unavailable": [],
           "repos": [], "swap": []}

    def add(kind, names):
        for name in names:
            if name not in out[kind]:
                out[kind].append(name)

    for item in ids or []:
        item = str(item)
        prefix, sep, raw = item.partition(":")
        if sep and prefix in RAW_PREFIXES:
            add(RAW_PREFIXES[prefix], [raw])
            continue
        pid = aliases.get(item, item)
        if pid not in catalog:
            add("unknown", [item])
            continue
        entry = catalog[pid] or {}
        key = next((k for k in keys if k in entry), None)
        if key is None:
            add("missing", [pid])
            continue
        value = entry[key]
        if value is None:
            add("unavailable", [pid])
        elif isinstance(value, dict) and "flatpak" in value:
            add("flatpak", [value["flatpak"]])
        elif isinstance(value, dict) and "pipx" in value:
            add("pipx", [value["pipx"]])
        else:
            repo = entry.get("repo") or []
            if isinstance(value, dict):
                repo = value.get("repo") or []
                value = value["native"]
            names = [str(v) for v in value] if isinstance(value, (list, tuple)) else [str(value)]
            add("native", names)
            if entry.get("swap"):
                add("swap", names)
            add("repos", [repo] if isinstance(repo, str) else list(repo))
    return out


def alpi_feature_ids(feature_packages, flags):
    """Package ids of the features that are on (feature_packages: feature -> list of ids)."""
    ids = []
    for name, pkgs in (feature_packages or {}).items():
        if flags.get(name):
            ids.extend(i for i in pkgs or [] if i not in ids)
    return ids


def alpi_repos(definitions, always, needed):
    """Order the repositories to enable: 'always' first (in its order), then the needed ones.

    Returns {"enabled": [definition + {"id": ...}, ...], "unknown": [ids with no definition]}.
    """
    enabled, unknown, seen = [], [], set()
    for rid in list(always or []) + list(needed or []):
        if rid in seen:
            continue
        seen.add(rid)
        if rid in (definitions or {}):
            enabled.append(dict(definitions[rid], id=rid))
        else:
            unknown.append(rid)
    return {"enabled": enabled, "unknown": unknown}


def alpi_canonical(ids, aliases=None):
    """Map ids through the aliases (raw prefixed names are kept as they are)."""
    aliases = aliases or {}
    return [aliases.get(str(i), str(i)) for i in ids or []]


def alpi_features(merged, hardware, detected):
    """Turn merged feature settings into booleans.

    Hardware features follow detection: 'auto' (or true) is on only when the hardware was
    detected, false vetoes it. Other features are plain booleans.
    """
    out = {}
    for name, value in merged.items():
        if name in hardware:
            out[name] = bool(detected.get(name)) and value is not False
        else:
            out[name] = bool(value)
    return out


def alpi_flatpak_overrides(layers, filesystem, selected):
    """Merge Flatpak override layers and keep the apps that are selected.

    layers:     list of {app id: [flatpak override flags]} (repo, desktop, user), merged in order;
    filesystem: {app id: [folders]}, the user's folder grants, turned into --filesystem=<folder>;
    selected:   Flatpak app ids in the resolved sets (only those get overrides).
    Returns {"apply": [{"app", "flags"}], "skipped": [app ids not selected],
             "invalid": ["<app>: <flag>" for flags not starting with "--"]}.
    """
    merged = {}
    sources = list(layers or []) + [
        {app: ["--filesystem=" + str(f) for f in folders or []] for app, folders in (filesystem or {}).items()}
    ]
    for layer in sources:
        for app, flags in (layer or {}).items():
            out = merged.setdefault(str(app), [])
            out.extend(str(f) for f in flags or [] if str(f) not in out)
    selected = set(selected or [])
    result = {"apply": [], "skipped": [], "invalid": []}
    for app, flags in merged.items():
        result["invalid"].extend(f"{app}: {f}" for f in flags if not f.startswith("--"))
        if app not in selected:
            result["skipped"].append(app)
        elif flags:
            result["apply"].append({"app": app, "flags": flags})
    return result


def alpi_luks_aliases(volumes):
    """open-<name> / close-<name> zsh aliases for LUKS volumes ({name: LUKS UUID}).

    The partition is found by its UUID (/dev/disk/by-uuid/<UUID>), so renumbered disks do not
    matter; udisksctl names the unlocked device /dev/mapper/luks-<UUID>. Names and UUIDs are
    validated in tasks/env_setup.yml before this runs.
    """
    lines = []
    for name, uuid in (volumes or {}).items():
        dev, mapper = f"/dev/disk/by-uuid/{uuid}", f"/dev/mapper/luks-{uuid}"
        lines.append(f'alias open-{name}="udisksctl unlock -b {dev}; udisksctl mount -b {mapper}"')
        lines.append(f'alias close-{name}="udisksctl unmount -b {mapper}; udisksctl lock -b {dev}"')
    return "\n".join(lines)


def alpi_invalid_luks(volumes):
    """Entries of luks_volumes ({name: LUKS UUID}) that cannot make safe aliases, as "name: value"."""
    name_re = re.compile(r"[A-Za-z0-9_-]+")
    uuid_re = re.compile(r"[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
    return [f"{name}: {uuid}" for name, uuid in (volumes or {}).items()
            if not name_re.fullmatch(str(name)) or not uuid_re.fullmatch(str(uuid))]


def alpi_pipx_name(spec):
    """The package name of a pipx/PyPI spec: "notebooklm-py[browser]" -> "notebooklm-py"."""
    return re.split(r"[\[<>=!~;@ ]", str(spec).strip(), maxsplit=1)[0]


class FilterModule(object):
    def filters(self):
        return {
            "alpi_resolve": alpi_resolve,
            "alpi_canonical": alpi_canonical,
            "alpi_features": alpi_features,
            "alpi_repos": alpi_repos,
            "alpi_feature_ids": alpi_feature_ids,
            "alpi_flatpak_overrides": alpi_flatpak_overrides,
            "alpi_luks_aliases": alpi_luks_aliases,
            "alpi_invalid_luks": alpi_invalid_luks,
            "alpi_pipx_name": alpi_pipx_name,
        }

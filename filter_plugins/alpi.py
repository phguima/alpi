# ALPI filters: resolve logical package ids through the catalog (see PROPOSAL.md, "Customization").

# Raw names bypass the catalog: "pkg:<native name>" or "flatpak:<app id>".
RAW_PREFIXES = {"pkg": "native", "flatpak": "flatpak"}


def alpi_resolve(ids, catalog, keys, aliases=None):
    """Resolve logical ids for the current distro.

    keys: catalog keys to try, most specific first (e.g. ["el10", "el", "all"]).
    Returns a dict:
      native / flatpak: names to install with the package manager / Flatpak;
      unknown:     ids missing from the catalog (user or repo error);
      missing:     ids in the catalog with no entry for any of the keys (catalog bug);
      unavailable: ids marked ~ (null) for this distro (skipped with a warning);
      repos:       repository ids that the resolved native packages need (an entry's 'repo'
                   key, a string or a list; Flatpak values need no repository);
      swap:        native names of entries with 'swap: true', which replace a conflicting
                   package (ffmpeg-free -> ffmpeg) and are installed first with allowerasing.
                   They are in 'native' too, so name checks and verification cover them.
    """
    aliases = aliases or {}
    out = {"native": [], "flatpak": [], "unknown": [], "missing": [], "unavailable": [], "repos": [], "swap": []}

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
        else:
            names = [str(v) for v in value] if isinstance(value, (list, tuple)) else [str(value)]
            add("native", names)
            if entry.get("swap"):
                add("swap", names)
            repo = entry.get("repo") or []
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


class FilterModule(object):
    def filters(self):
        return {
            "alpi_resolve": alpi_resolve,
            "alpi_canonical": alpi_canonical,
            "alpi_features": alpi_features,
            "alpi_repos": alpi_repos,
            "alpi_feature_ids": alpi_feature_ids,
        }

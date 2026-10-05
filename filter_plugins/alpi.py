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
      unavailable: ids marked ~ (null) for this distro (skipped with a warning).
    """
    aliases = aliases or {}
    out = {"native": [], "flatpak": [], "unknown": [], "missing": [], "unavailable": []}

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
        elif isinstance(value, (list, tuple)):
            add("native", [str(v) for v in value])
        else:
            add("native", [str(value)])
    return out


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
        }

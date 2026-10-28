# ALPI filters: resolve logical package ids through the catalog (see PROPOSAL.md, "Customization").

import base64
import binascii
import json
import re

# Raw names bypass the catalog: "pkg:<native name>", "flatpak:<app id>" or "pipx:<PyPI spec>".
RAW_PREFIXES = {"pkg": "native", "flatpak": "flatpak", "pipx": "pipx"}


def alpi_resolve(ids, catalog, keys, aliases=None):
    """Resolve logical ids for the current distro.

    keys: catalog keys to try, most specific first (e.g. ["el10", "el", "all"]).
    Returns a dict:
      native / flatpak / pipx: names to install with the package manager / Flatpak / pipx (pipx
                   values are PyPI specs, extras included: "markitdown[all]");
      upstream:    source ids ({upstream: <id>}, defined in upstream_sources) that roles/upstream
                   installs from their vendor's releases where the distro has no package;
      unknown:     ids missing from the catalog (user or repo error);
      missing:     ids in the catalog with no entry for any of the keys (catalog bug);
      unavailable: ids marked ~ (null) for this distro (skipped with a warning);
      repos:       repository ids that the resolved native packages need (an entry's 'repo'
                   key, a string or a list; Flatpak values need no repository). A per-distro
                   value {native: <name or list>, repo: <id or list>} names its own
                   repository instead, for a source that only one distro needs;
      swap:        native names of entries with 'swap: true', which replace a conflicting
                   package (ffmpeg-free -> ffmpeg) and are installed first with allowerasing.
                   They are in 'native' too, so name checks and verification cover them. A
                   per-distro value {native: …, swap: true|false} overrides the entry's 'swap'
                   for that distro.
    """
    aliases = aliases or {}
    out = {"native": [], "flatpak": [], "pipx": [], "upstream": [], "unknown": [], "missing": [],
           "unavailable": [], "repos": [], "swap": []}

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
        elif isinstance(value, dict) and "upstream" in value:
            add("upstream", [str(value["upstream"])])
        else:
            repo = entry.get("repo") or []
            swap = entry.get("swap")
            if isinstance(value, dict):
                repo = value.get("repo") or []
                swap = value.get("swap", swap)
                value = value["native"]
            names = [str(v) for v in value] if isinstance(value, (list, tuple)) else [str(value)]
            add("native", names)
            if swap:
                add("swap", names)
            add("repos", [repo] if isinstance(repo, str) else list(repo))
    return out


def alpi_support(matrix, distro, version, major):
    """Whether the distro is in the support matrix, and the matrix as text for the error.

    matrix: {distro: {min: N, max: N}} (major versions, inclusive) or {distro: {version: "26.04"}}
    (that exact distribution_version: Ubuntu's major is 26 for both 26.04 and 26.10).
    Returns {"supported": bool, "listed": "Fedora 41-44, AlmaLinux 10, Ubuntu 26.04"}.
    """
    def text(name, entry):
        if "version" in entry:
            return f"{name} {entry['version']}"
        lo, hi = entry["min"], entry["max"]
        return f"{name} {lo}" if lo == hi else f"{name} {lo}-{hi}"

    entry = (matrix or {}).get(distro)
    if entry is None:
        supported = False
    elif "version" in entry:
        supported = str(version) == str(entry["version"])
    else:
        supported = str(major).isdigit() and int(entry["min"]) <= int(major) <= int(entry["max"])
    return {"supported": supported,
            "listed": ", ".join(text(name, e) for name, e in (matrix or {}).items())}


def alpi_apt_components(text, components, release):
    """Add the missing components to the distro's own apt sources, in either format.

    text: /etc/apt/sources.list (one-line) or a deb822 .sources file. Only the entries whose suite
    is the release or one of its pockets (trixie, trixie-updates, trixie-security) change; cdrom:
    lines, comments and other repositories are kept as they are. Missing components are appended,
    the existing ones keep their order. Returns the new text (the same text when nothing is missing).
    """
    def ours(suite):
        return suite == release or suite.startswith(release + "-")

    def merged(present):
        return present + [c for c in components if c not in present]

    lines = str(text).split("\n")
    if any(re.match(r"(?i)^(Types|URIs|Suites):", l) for l in lines):
        # deb822: stanzas separated by blank lines; change Components where Suites is ours
        out, stanza = [], []
        for line in lines + [""]:
            if line.strip():
                stanza.append(line)
                continue
            suites = next((l.split(":", 1)[1].split() for l in stanza if re.match(r"(?i)^Suites:", l)), [])
            if any(ours(s) for s in suites):
                stanza = [f"Components: {' '.join(merged(l.split(':', 1)[1].split()))}"
                          if re.match(r"(?i)^Components:", l) else l for l in stanza]
            out.extend(stanza + [line])
            stanza = []
        return "\n".join(out[:-1])
    out = []
    for line in lines:
        m = re.match(r"^(deb(?:-src)?\s+(?:\[[^\]]*\]\s+)?)(\S+)\s+(\S+)((?:\s+\S+)*)\s*$", line)
        if m and not m.group(2).startswith("cdrom:") and ours(m.group(3)):
            line = f"{m.group(1)}{m.group(2)} {m.group(3)} {' '.join(merged(m.group(4).split()))}"
        out.append(line)
    return "\n".join(out)


def alpi_apt_simulation(lines):
    """Read the output of `apt-get install -s <names>` (LC_ALL=C).

    missing: names apt does not know ("Unable to locate package") or knows only as a name other
    packages refer to ("has no installation candidate"); apt reports them all and resolves
    nothing. unresolved: when nothing is missing, the "unmet dependencies" block and the other
    E: lines (no transaction was reached). W: lines are not errors.
    """
    lines = [str(l) for l in lines or []]
    missing = []
    for line in lines:
        m = re.match(r"^E: (?:Unable to locate package (\S+)|Package '([^']+)' has no installation candidate)", line)
        if m and (m.group(1) or m.group(2)) not in missing:
            missing.append(m.group(1) or m.group(2))
    if missing:
        return {"missing": missing, "unresolved": []}
    unresolved, block = [], False
    for line in lines:
        if line.startswith("The following packages have unmet dependencies:"):
            block = True
        elif line.startswith("E: "):
            block = False
            unresolved.append(line)
        elif block and line.strip():
            unresolved.append(line.strip())
    return {"missing": [], "unresolved": unresolved}


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


def alpi_flatpak_overrides(layers, filesystem, selected, reset_if=None):
    """Merge Flatpak override layers and keep the apps that are selected.

    layers:     list of {app id: [flatpak override flags]} (repo, desktop, user), merged in order;
    filesystem: {app id: [folders]}, the user's folder grants, turned into --filesystem=<folder>;
    selected:   Flatpak app ids in the resolved sets (only those get overrides);
    reset_if:   {app id: text}: a selected app's override file is reset before its flags are
                applied when it contains that text (a workaround that no longer applies, such as
                the cedilla's XWayland flags). Those apps get an entry even without flags.
    Returns {"apply": [{"app", "flags", "reset_if"}], "skipped": [app ids not selected],
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
    reset_if = {str(app): str(text) for app, text in (reset_if or {}).items()}
    for app in reset_if:
        merged.setdefault(app, [])
    selected = set(selected or [])
    result = {"apply": [], "skipped": [], "invalid": []}
    for app, flags in merged.items():
        result["invalid"].extend(f"{app}: {f}" for f in flags if not f.startswith("--"))
        if app not in selected:
            result["skipped"].append(app)
        elif flags or app in reset_if:
            result["apply"].append({"app": app, "flags": flags, "reset_if": reset_if.get(app, "")})
    return result


def _version(text):
    """Upstream version numbers: a dpkg epoch ('4:') and the revision or release after the first
    '-' are dropped, so '4:6.6.6-0ubuntu0.1' reads as (6, 6, 6)."""
    upstream = re.sub(r"^\d+:", "", str(text).strip()).split("-", 1)[0]
    return tuple(int(n) for n in re.findall(r"\d+", upstream))


def alpi_cedilla_xwayland(setting, is_kde, kwin_version, below):
    """Whether the cedilla workaround runs Chromium/Electron apps on XWayland.

    On native Wayland they ignore ~/.XCompose under KWin 6.6 (EL10, Fedora 44 before its 6.7
    update) and type "ć". Only on KDE; setting (cedilla_xwayland): "auto" follows the KWin version
    (older than 'below'; no KWin installed means no), true/false force it on KDE.
    """
    if not is_kde or setting is False:
        return False
    if setting is True:
        return True
    return bool(_version(kwin_version)) and _version(kwin_version) < _version(below)


def _gib(size):
    return f"{size / 2**30:.1f} GiB"


def alpi_zram_plan(setting, swaps, zswap, generator, etc_conf, marker, hibernate, mem_mb):
    """What roles/memory does with zram, from what the machine already has.

    setting:   zram (auto/true/false);
    swaps:     stdout of 'swapon --show --raw --noheadings --bytes --output NAME,TYPE,SIZE,PRIO';
    zswap:     /sys/module/zswap/parameters/enabled ("Y"/"N"; "" when there is no zswap);
    generator: zram-generator is installed;
    etc_conf:  slurp result of /etc/systemd/zram-generator.conf ('content' when it exists); a
               file without the marker is the user's own configuration;
    hibernate: the machine hibernates, so its disk swap must hold all of RAM (zram cannot);
    mem_mb:    RAM size.
    A zram device that zram-generator did not make, or the user's own configuration, is left
    alone; so is zram while zswap is on (it would compress every page twice). auto says why in
    'notes'; true/false, which ALPI cannot honor there, get an 'error'.
    Returns {"state": "on"|"off"|"skip", "error", "notes", "summary", "zram", "disk",
             "own_mask": /etc/systemd/zram-generator.conf is ALPI's switch-off file,
             "mask": write that file (off, with zram-generator installed),
             "hibernate_reminder": hibernate is on and disk swap is smaller than RAM}.
    """
    zram, disk = [], []
    for line in str(swaps or "").splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        name = fields[0].replace("\\x20", " ")
        dev = {"name": name, "type": fields[1], "size": int(fields[2]), "prio": int(fields[3])}
        (zram if re.fullmatch(r"/dev/zram\d+", name) else disk).append(dev)
    conf = None
    if isinstance(etc_conf, dict) and etc_conf.get("content") is not None:
        conf = base64.b64decode(etc_conf["content"]).decode(errors="replace")
    own_mask = conf is not None and marker in conf
    notes, error, state = [], "", "on"

    def leave(why):
        nonlocal state, error
        state = "skip"
        if setting == "auto":
            notes.append(why + " ALPI leaves it alone.")
        else:
            error = f"zram: {str(setting).lower()} cannot be applied: {why}"

    if conf is not None and not own_mask:
        leave("/etc/systemd/zram-generator.conf is your own zram configuration.")
    elif zram and not generator:
        leave(f"{', '.join(d['name'] for d in zram)} was set up by something other than zram-generator.")
    elif setting is False:
        state = "off"
    elif str(zswap).strip() == "Y":
        leave("zswap is on; with zram too, every swapped page would be compressed twice. To use "
              "zram, turn zswap off (kernel argument zswap.enabled=0).")

    ram = int(mem_mb) * 2**20
    disk_total = sum(d["size"] for d in disk)
    summary = [f"RAM {_gib(ram)}"]
    summary += [f"zram {d['name']}: {_gib(d['size'])}, priority {d['prio']}" for d in zram]
    summary += [f"disk swap {d['name']} ({d['type']}): {_gib(d['size'])}, priority {d['prio']}"
                for d in disk]
    if not zram and not disk:
        summary.append("no swap")
    summary.append(f"zram: {state}")
    if state == "on" and disk:
        notes.append("Disk swap stays: zram (priority 100) is used first, the disk when zram is full.")
    return {"state": state, "error": error, "notes": notes, "summary": summary, "zram": zram,
            "disk": disk, "own_mask": own_mask, "mask": state == "off" and generator,
            "hibernate_reminder": bool(hibernate) and disk_total < ram}


def _exec_flag(text, flag, add):
    """Add flag after the command of every Exec= line (once), or remove it from them."""
    out = []
    for line in text.splitlines(keepends=True):
        if line.startswith("Exec="):
            body = line.rstrip("\r\n")
            end = line[len(body):]
            words = body.split(" ")
            if add and flag not in words:
                words.insert(1, flag)
            elif not add:
                words = [w for w in words if w != flag]
            line = " ".join(words) + end
        out.append(line)
    return "".join(out)


def alpi_xwayland_entries(system, user, flag, enabled, marker):
    """What to do with the user's copies of system menu entries for the XWayland flag.

    system, user: slurp results (each with 'item', the entry's file name, and 'content' when the
    file exists) of /usr/share/applications/<name> and ~/.local/share/applications/<name>.
    A copy is ALPI's when it has the marker, or when it is the system entry plus the flag (AAPI
    made those, without a marker). On: ALPI's copy is rebuilt from the system entry (or removed
    when the app is gone); a user's own copy only gets the flag. Off: ALPI's copy is removed and
    the flag is taken out of a user's own copy.
    Returns [{"name", "state": "present"|"absent", "content"}] for files that must change.
    """
    def text(result):
        return base64.b64decode(result["content"]).decode() if result.get("content") else None

    users = {str(r["item"]): text(r) for r in user or []}
    plan = []
    for result in system or []:
        name, sys_text = str(result["item"]), text(result)
        usr = users.get(name)
        ours = usr is not None and (marker in usr or (sys_text is not None
                                                      and _exec_flag(usr, flag, False) == sys_text))
        if usr is None and not (enabled and sys_text is not None):
            continue
        if ours and not (enabled and sys_text is not None):
            plan.append({"name": name, "state": "absent", "content": ""})
            continue
        if enabled and (usr is None or ours):
            content = f"# {marker}\n" + _exec_flag(sys_text, flag, True)
        else:
            content = _exec_flag(usr, flag, enabled)
        if content != usr:
            plan.append({"name": name, "state": "present", "content": content})
    return plan


_STEAM_GPU_KEYS = ["PrefersNonDefaultGPU=true", "X-KDE-RunOnDiscreteGpu=true"]


def alpi_steam_launcher(system, user, enabled, marker):
    """What to do with the user's Steam launcher (~/.local/share/applications/steam.desktop).

    system, user: the system and user steam.desktop texts (None when missing). enabled: Steam
    should start on the NVIDIA GPU through the desktop (the driver selected, and a system launcher
    that does not ask for it, as Debian's and Ubuntu's). A launcher is ALPI's when it has the
    marker, or carries the PRIME offload variables (ALPI's and AFPI's old copies). Wanted: ALPI's
    copy is the system launcher plus PrefersNonDefaultGPU and X-KDE-RunOnDiscreteGpu in its
    [Desktop Entry], no variables; a user's own launcher is left alone. Not wanted: ALPI's goes.
    Returns {"state": "present"|"absent"|"keep", "content"}.
    """
    ours = user is not None and (marker in user or "Exec=env __NV_PRIME_RENDER_OFFLOAD=1 " in user)
    wanted = enabled and system is not None and _STEAM_GPU_KEYS[0] not in system
    if wanted and (user is None or ours):
        out, group = [f"# {marker}"], None
        for line in system.splitlines():
            if line.startswith("["):
                group = line.strip()
            if group == "[Desktop Entry]" and line.split("=", 1)[0] in ("PrefersNonDefaultGPU", "X-KDE-RunOnDiscreteGpu"):
                continue
            out.append(line)
            if line.strip() == "[Desktop Entry]":
                out.extend(_STEAM_GPU_KEYS)
        content = "\n".join(out) + "\n"
        return {"state": "keep" if content == user else "present", "content": content}
    if ours and not wanted:
        return {"state": "absent", "content": ""}
    return {"state": "keep", "content": ""}


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


def alpi_zsh_aliases(definitions, enabled, installed, root=False):
    """The alias lines for one .zshrc from the definitions ({name: {cmd, root, requires}},
    group_vars/all/zsh.yml), in their order.

    An alias is left out when switched off in enabled ({name: bool}, the picker's and custom.yml's
    choices), when its requires (a catalog id or feature) is not in installed, and in root's
    .zshrc (root=True) unless its definition says root: true. Single-quoted, so the command is
    expanded when the alias runs.
    """
    lines = []
    for name, d in (definitions or {}).items():
        if not (enabled or {}).get(name, True) or (root and not d.get("root")):
            continue
        if d.get("requires") and d["requires"] not in (installed or []):
            continue
        cmd = str(d["cmd"]).replace("'", "'\\''")
        lines.append(f"alias {name}='{cmd}'")
    return "\n".join(lines)


def alpi_pipx_name(spec):
    """The package name of a pipx/PyPI spec: "notebooklm-py[browser]" -> "notebooklm-py"."""
    return re.split(r"[\[<>=!~;@ ]", str(spec).strip(), maxsplit=1)[0]


def alpi_appimage_release(manifest):
    """The AppImage in an electron-updater manifest (latest-linux.yml, already parsed).

    Returns {"version", "url", "sha512"} with the checksum in hex (the manifest has it in base64,
    get_url wants hex), or {"error": <message>} when there is no usable AppImage entry.
    """
    files = (manifest or {}).get("files") if isinstance(manifest, dict) else None
    entry = next((f for f in files or [] if isinstance(f, dict)
                  and str(f.get("url", "")).endswith(".AppImage")), None)
    if entry is None:
        return {"error": "no AppImage in the manifest's files"}
    try:
        digest = base64.b64decode(str(entry.get("sha512", "")), validate=True)
    except (binascii.Error, ValueError):
        digest = b""
    if len(digest) != 64:
        return {"error": f"no valid sha512 for {entry['url']}"}
    return {"version": str(manifest.get("version", "")), "url": str(entry["url"]), "sha512": digest.hex()}


def _release_asset(release, pattern):
    """The first asset of a release whose name matches 'pattern' (regex), or an error message."""
    try:
        regex = re.compile(str(pattern))
    except re.error as exc:
        return None, f"bad asset pattern {pattern!r}: {exc}"
    asset = next((a for a in release.get("assets") or [] if isinstance(a, dict)
                  and regex.search(str(a.get("name", ""))) and a.get("browser_download_url")), None)
    if asset is None:
        return None, f"no asset matching {pattern!r} in {release['tag_name']}"
    return asset, None


def alpi_github_release(release, pattern, checksum_pattern=""):
    """The asset of a release (the API's JSON, parsed) whose name matches 'pattern' (regex).

    GitHub, Gitea and Forgejo answer in the same shape (tag_name, assets[].browser_download_url);
    only GitHub publishes digests. Returns {"tag", "name", "url", "checksum"}: checksum is what
    get_url takes, the asset's digest ("sha256:<hex>"), else, with 'checksum_pattern', the URL
    of the asset holding its sha256 ("sha256:<url>", Gitea's .sha256 files), else "" (older
    GitHub assets, releases with no checksum). {"error": <message>} when the release has no tag,
    or no asset (or checksum asset) matching.
    """
    if not isinstance(release, dict) or not release.get("tag_name"):
        return {"error": "not a release (no tag_name)"}
    asset, error = _release_asset(release, pattern)
    if error:
        return {"error": error}
    digest = str(asset.get("digest") or "")
    checksum = digest if re.fullmatch(r"sha256:[0-9a-f]{64}", digest) else ""
    if not checksum and checksum_pattern:
        sums, error = _release_asset(release, checksum_pattern)
        if error:
            return {"error": error}
        checksum = "sha256:" + str(sums["browser_download_url"])
    return {"tag": str(release["tag_name"]), "name": str(asset["name"]),
            "url": str(asset["browser_download_url"]), "checksum": checksum}


def alpi_upstream_missing(results, sources):
    """Upstream source ids whose release lookup shows the source is wrong.

    results: the uri loop results of the release lookups (item = source id); sources:
    upstream_sources. A 404, or a 200 whose release has no asset matching the source's pattern
    (or its checksum_asset pattern), is missing; any other status (offline, rate limit) is not decided here.
    """
    missing = []
    for res in results or []:
        sid, status = res.get("item"), res.get("status")
        if status == 404:
            missing.append(sid)
        elif status == 200:
            try:
                release = json.loads(res.get("content") or "")
            except ValueError:
                release = None
            source = sources.get(sid) or {}
            if "error" in alpi_github_release(release, source.get("asset", ""),
                                              source.get("checksum_asset", "")):
                missing.append(sid)
    return missing


class FilterModule(object):
    def filters(self):
        return {
            "alpi_resolve": alpi_resolve,
            "alpi_support": alpi_support,
            "alpi_apt_components": alpi_apt_components,
            "alpi_apt_simulation": alpi_apt_simulation,
            "alpi_canonical": alpi_canonical,
            "alpi_features": alpi_features,
            "alpi_repos": alpi_repos,
            "alpi_feature_ids": alpi_feature_ids,
            "alpi_flatpak_overrides": alpi_flatpak_overrides,
            "alpi_cedilla_xwayland": alpi_cedilla_xwayland,
            "alpi_zram_plan": alpi_zram_plan,
            "alpi_xwayland_entries": alpi_xwayland_entries,
            "alpi_steam_launcher": alpi_steam_launcher,
            "alpi_luks_aliases": alpi_luks_aliases,
            "alpi_invalid_luks": alpi_invalid_luks,
            "alpi_zsh_aliases": alpi_zsh_aliases,
            "alpi_pipx_name": alpi_pipx_name,
            "alpi_appimage_release": alpi_appimage_release,
            "alpi_github_release": alpi_github_release,
            "alpi_upstream_missing": alpi_upstream_missing,
        }

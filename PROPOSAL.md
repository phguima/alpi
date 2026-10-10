# ALPI — Ansible Linux Post-Install

Architecture proposal (2026-10-05). Revised after an adversarial review. Profiles replaced by the
package picker on 2026-10-08 (see "Decisions (2026-10-08)").

## Goal

A single project that detects the running distro and applies the right post-install. Today it
would be the union of **AFPI** (Fedora, personal machine `noir`) and **AAPI** (AlmaLinux 10, work
machine). Later it should take other distros (Debian, Ubuntu…).

## Starting point

AFPI and AAPI have the same structure and share 6 roles (`update`, `hardware`, `common`, `apps`,
`desktop`, `ai_tools`). AFPI has two more: `nvidia` and `akmods_mok`. The two are already drifting
apart. For example, AAPI did not get the icon-ownership fix (`af80a16`) nor several
`check_mode: false`.

| Difference | Example | Nature |
|---|---|---|
| Package name | `vim` → `vim-enhanced`, `shellcheck` → `ShellCheck`, `p7zip` → `7zip` | data per distro |
| Package missing in the distro | Telegram/Drawy via Flatpak on EL10, Roboto from upstream, argyllcms/chkrootkit/unhide | data per distro |
| Repositories | RPM Fusion + COPR (Fedora); CRB + EPEL + RPM Fusion EL + Oracle (Alma) | tasks per family |
| Behavior | dnf5 × dnf4 (`repo list --json` × `repolist`), VirtualBox akmod + kmodgenca × Oracle + own key, `@groups`, `.i686`, `allowerasing` | tasks per distro |
| Tooling | `ansible` × `ansible-core`, `community.general <12` on EL10 (ansible-core 2.16) | bootstrap |
| Hardware | NVIDIA, ASUS, AMD freeworld | detected |
| Machine/user | hostname, `open/close-thevoid` aliases with `noir`'s LUKS UUID | per machine |

## Chosen approach: unification (B)

The discarded alternative (A) would be a thin dispatcher that calls AFPI or AAPI as submodules. It
keeps the duplication, and every new distro would become a whole repository.

### Three independent axes

1. **Distro**: detected from `ansible_facts`.
2. **Hardware**: detected (NVIDIA, ASUS, AMD, Secure Boot). The user can **only veto** it
   (`nvidia: auto | false`).
3. **Machine/user**: lives in `host_vars`, outside git: the hostname and git identity
   (`bootstrap.yml`), the package and feature choice (`selection.yml`, written by the picker) and
   hand-written settings (`custom.yml`). The thevoid UUID leaves the repository and comes here
   (2026-10-08: `luks_volumes: {thevoid: <UUID>}` in `custom.yml` generates `open-thevoid` /
   `close-thevoid`, addressing the partition by UUID instead of `/dev/nvme1n1p3`).

There are no profiles (removed on 2026-10-08). What a profile used to decide is a choice made on
the machine: the hostname is managed only when one is given, and packages and features are picked
from what the running distro offers (see "Package picker").

### Structure

```
alpi/
  bootstrap.sh              # reads /etc/os-release → installs ansible via dnf/apt; pins collections per version
  site.yml
  catalog.yml               # logical package ids → name per distro (see "Customization")
  tasks/env_setup.yml       # support matrix (assert) → detection → group_by → package resolution
  group_vars/
    all/                    # shared: user, git, flatpaks, zsh, ai_tools; secrets.yml (vault)
    os_Fedora/  os_AlmaLinux_10/  os_Debian_13/ …
  pick.py                   # package picker (run by bootstrap, or on its own)
  host_vars/127.0.0.1/      # git-ignored
    bootstrap.yml           # written by bootstrap (hostname, git identity)
    selection.yml           # written by pick.py (differences from the defaults)
    custom.yml              # written by the user (see custom.yml.example)
  roles/
    repos/                  # NEW, runs first: rpmfusion/epel/crb/copr | apt sources/extrepo/PPA
    update/ common/ apps/ desktop/ hardware/ nvidia/ ai_tools/
    mok/                    # separate signers: kmodgenca (/etc/pki/akmods), Oracle vboxdrv
                            # (/var/lib/shim-signed/mok), DKMS (/var/lib/dkms/mok.*). Keeps the
                            # current paths so existing machines need no re-enrollment.
```

Inside each role, the specific tasks live in `tasks/{Fedora,RedHat,Debian}.yml`.
`ansible.builtin.package` is used only for plain package lists. dnf and apt stay explicit where the
behavior differs.

### Design rules

- **Precedence:** do not use `include_vars` for distro data, because it has higher priority than
  `host_vars` and would silently override the user. Instead, `group_by` creates dynamic groups
  (`os_<distro>`, `os_<distro>_<major>`) and the data lives in `group_vars/`. That keeps `host_vars` and `-e` on top. Layers never share a key (each has its own
  `packages_*`/`features_*` names), so the order between groups does not matter;
  `ansible_group_priority` would not help anyway, since it only works in the inventory source.
- **Explicit support:** an allowlist of (distro, version) with an assert before loading any
  variable. No silent fallback by `os_family`: Fedora, Rocky and CentOS Stream have
  `os_family = RedHat`, and Ubuntu falls into `Debian`.
- **Facts:** `inject_facts_as_vars = False` still holds, so always `ansible_facts[...]`.
- **Ansible:** use the distro's own ansible-core, with the code written for the lowest supported
  version (today 2.16, EL10's). Re-evaluate a pinned venv if some distro ships an older version.

## Package customization

### Two levels

- **Features**: items that have configuration tasks (virtualbox, steam, vscode, brave, gh,
  antigravity, clamav, nvidia, asus…). Switched on and off by a flag. A feature is **never** turned
  off by deleting a package name.
- **Packages**: plain items, with no configuration, resolved through the catalog.

### Catalog (in the repository)

```yaml
# catalog.yml: logical id -> package in each distro
vim:      {Fedora: vim, RedHat: vim-enhanced, Debian: vim}
7zip:     {Fedora: [p7zip, p7zip-plugins], RedHat: [7zip, 7zip-standalone]}
telegram: {Fedora: telegram-desktop, RedHat: {flatpak: org.telegram.desktop}}
steam:    {Fedora: steam, RedHat: ~}     # ~ = unavailable: skip and warn
aliases:  {p7zip: 7zip}                  # renamed ids still resolve
```

### Repositories and feature packages (added 2026-10-05, section 2)

- A catalog entry names the repository its native packages need: `brave: {all: [brave-browser,
  brave-origin], repo: brave-browser}`. Repositories are defined by id (`alpi_repos_common` in
  `group_vars/all/repos.yml`, `alpi_repos_os` in `group_vars/os_*`) with a type: `rpm` (release
  package by URL), `package`, `dnf_config` (CRB), `yum` (repo file) or `copr`.
- `roles/repos` enables the distro's `alpi_repos_always` first, in order (RPM Fusion on Fedora;
  CRB, EPEL, RPM Fusion EL on AlmaLinux), then only the repositories the selected packages need.
  Skipping `brave` means the Brave repository is never added. A repository id with no definition
  for the distro is a catalog bug and stops the run in `env_setup`.
- Features add package sets while they are on (`feature_packages: {asus: [asusctl, …]}`), so
  `features: {asus: false}` drops the packages and, through them, the ASUS COPR.
- (2026-10-06) `swap: true` marks a catalog entry that replaces a conflicting package
  (`ffmpeg-free` → `ffmpeg`, `mesa-va-drivers-freeworld`). `roles/packages` installs those first
  with `allowerasing`, so AFPI's separate "swap" tasks become catalog data and get the same name
  checks. Intel and AMD video acceleration are hardware features (`intel`, `amd`) with
  `feature_packages`, like ASUS. A package that exists on EL but is deliberately left out there
  (RPM Fusion's `@multimedia`, which breaks against EPEL) goes in `packages_os`, not `~`.
- (2026-10-06) NVIDIA: the driver, build, Vulkan and VA-API packages are catalog ids in
  `feature_packages.nvidia` (Fedora only). `roles/akmods_mok` runs before `roles/packages` when
  Secure Boot is on and any `akmod-*` package was resolved, which replaces AFPI's string match and
  will cover `akmod-VirtualBox` without changes. `roles/nvidia` rebuilds with akmods only when no
  module exists for the running kernel (AFPI rebuilt on every run until the reboot).
- (2026-10-06) VirtualBox: a plain feature (`virtualbox`, on by default). The catalog names
  `akmod-VirtualBox` on Fedora, so `roles/akmods_mok` picks it up; on EL a per-distro value
  `{native: […], repo: virtualbox}` adds Oracle's repository only there. `roles/virtualbox`
  (before `roles/packages`) creates the Oracle signing key with Secure Boot and the groups.

- (2026-10-09) Python apps installed with pipx are a third kind of catalog value,
  `{pipx: "<PyPI spec>"}` (extras included, "markitdown[all]"), next to native names and
  `{flatpak: …}`; `pipx:<spec>` is the raw prefix. They are installed for the user by
  `roles/pipx`, checked on PyPI with the other name checks, and picked like any package.
- (2026-10-10) `{upstream: <source id>}` is a fourth kind of catalog value, for software the
  distro does not package (Roboto on EL, from its GitHub release). Sources are data
  (`upstream_sources`, with a type per install method) and `roles/upstream` installs them by
  root. The id stays an ordinary catalog id: selected, skipped, picked and gated on like any other,
  and `packages_absent` removes it. AAPI's warn-and-keep when GitHub cannot be reached stays.
- (2026-10-10) AI tools are features without catalog packages: `claude_code`, `antigravity_cli`
  and `antigravity_ide` (on by default, as AFPI/AAPI install all three). Their vendors ship
  installers and self-updating binaries, not packages, so `roles/ai_tools` runs each installer
  once (only when the binary is missing) and lets the tool update itself; the IDE's AppImage comes
  from the manifest the app polls, checked against its sha512. AFPI's `antigravity_ide_install`
  flag is replaced by the feature. A feature without packages is the one case where a role gates
  on the flag itself; the picker labels it from `feature_descriptions`.

### User file (outside git)

```yaml
# host_vars/127.0.0.1/custom.yml
features:      {virtualbox: false, clamav: false}
packages_add:  [vim, "rpm:sqlitebrowser", "flatpak:org.gimp.GIMP"]   # prefix = raw name, bypasses the catalog
packages_skip: [discord]
packages_absent: [akregator]   # explicit uninstall (see Removal)
```

### Rules

- **Merging:** each layer uses its own keys (`packages_base`, `packages_selection_add`,
  `packages_selection_skip`, `packages_add`, `packages_skip`). Files in the same `host_vars`
  directory do not merge a shared key (the last one loaded wins), so `selection.yml` and
  `custom.yml` never share one. A single `set_fact` builds the final list:
  `(base + selection_add + add) | unique | difference(selection_skip + skip)`. The user layer is applied last. Never use
  `hash_behaviour`.
- **Validation** (in `env_setup`, before anything changes on the system):
  - an unknown id stops the run and lists all unknown ids;
  - an id that is `~` on the current distro is skipped with a warning (or fails, with
    `strict: true`);
  - every native name (catalog and `pkg:`) and Flatpak id is checked to exist at the start of the
    `packages` role, before anything from the lists is installed: a `dnf install --assumeno` dry
    run (resolves provides, same message on dnf4/dnf5) and `flatpak remote-info flathub`. Not in
    `env_setup`, because EPEL/RPM Fusion/COPR names only resolve after the `repos` role ran.
- **Isolation:** the user's extras are installed in a separate task, after the base, so a typo does
  not break the whole install.
- **Removal:** `skip` means "do not install", **never** "uninstall". Dropping a package from the
  defaults does not uninstall it either. There is no record of what ALPI installed. Uninstalling
  happens only through `packages_absent` (catalog ids or prefixed raw names, same validation),
  with `autoremove: false` so dependencies are not cascaded away. An id in both an install list
  and `packages_absent` is an error.
- **Separate files:** bootstrap and the picker rewrite their own files (`bootstrap.yml`,
  `selection.yml`) with PyYAML, which would wipe hand-written comments. That is why `custom.yml` is
  a separate file. Since all three stay outside git, `git pull` never conflicts.

### Package picker (2026-10-08)

`pick.py` (Python, run by `bootstrap.sh` or on its own) replaces the profiles. The 2026-10-05
objection to a picker was that it would re-implement the catalog in bash; in Python it reuses the
catalog files and `filter_plugins/alpi.py` (`alpi_resolve`), so it lists exactly what the playbook
would resolve.

- **Only what this system offers:** ids that are `~` on the running distro are hidden, so are the
  packages of a desktop that is not running (same `XDG_CURRENT_DESKTOP` rule as `env_setup`) and
  features whose packages are all unavailable (Steam on EL). Packages a feature owns
  (`feature_packages`) are switched through the feature, not listed on their own.
- **Hardware is not listed:** it follows detection; vetoes stay in `custom.yml`. The picker would
  have to repeat the detection (`lspci`) to show it.
- **Defaults pre-checked:** `packages_base` + `packages_os` + the running desktop's list, and
  `features_default`.
- **Stored as differences** in `selection.yml`: `packages_selection_add`, `packages_selection_skip`,
  `features_selection`. Defaults added to the repository later still arrive with `git pull`.
  Saved entries for ids the picker does not list this time (another desktop's packages) are kept;
  ids no longer in the catalog are dropped with a warning (the playbook fails on them until then).
- **Interface:** `whiptail` checklists (bootstrap installs `newt`), plain prompts otherwise or with
  `ALPI_PICKER=text`. Cancel leaves `selection.yml` as it was. No terminal, no picker: the
  playbook uses the defaults (and Molecule never runs it).

### Flatpak permissions (already in AFPI/AAPI)

On 2026-10-05 AFPI and AAPI gained `flatpak_filesystem_overrides` (`group_vars/all/all.yml`) and the
task `Software | Grant extra folders to flatpak applications` (`roles/apps`). It is an
app → folders map, applied with `flatpak override --user --filesystem=…`:

```yaml
flatpak_filesystem_overrides:
  com.rtosta.zapzap:
    - "{{ user_home }}/wks:ro"   # drag files from ~/wks into ZapZap
```

The reason: the Flatpak sandbox only sees granted folders. A file dragged from anywhere else
reaches the app as a path it cannot open (ZapZap says the file "has no content"). The file picker
goes through the portal and needs no grant.

In ALPI:
- The folders are the user's (`~/wks` is personal), so the map goes into `custom.yml`. The
  repository ships the map empty, with ZapZap in `custom.yml.example`.
- The fixed Bitwarden and Zoom overrides (Wayland, cedilla) can become the same mechanism,
  generalized to `flatpak_overrides: {app: [flags]}` and applied only when the app is in the
  resolved set.
- (2026-10-08, done) Layers, each with its own key: `flatpak_overrides_kde` in
  `group_vars/all/flatpak.yml` (Bitwarden, Zoom; KDE sessions only, as in AFPI), then the user's
  `flatpak_overrides` (flags) and `flatpak_filesystem_overrides` (folders, AFPI's key) in
  `custom.yml`. Flags add up per app; a flag not starting with `--` stops the run in `resolve`.
  Only apps in the resolved Flatpak sets get overrides, so skipping an app skips them. The task
  reports a change only when the override file differs (AFPI always reported none). Removing an
  entry does not undo it: `flatpak override --user --reset <app>`.

### Traps in the current code to fix during migration

- The VirtualBox gate is a string match: `'VirtualBox' in dnf_packages_common`
  (`afpi/roles/apps/tasks/main.yml:25`).
- `clamav-freshclam` is enabled unconditionally: if ClamAV is skipped, the run breaks.
- The Bitwarden and Zoom Flatpak overrides run even when those apps are not installed.

Each of these becomes a feature or is guarded by the resolved package set.

## Tests

- **Golden test:** a play that only prints the resolved package, flatpak and feature sets for each
  (distro, DE, selection). The output is compared with what AFPI and AAPI install today. This is what
  proves parity.
- **Podman containers** (`fedora:44`, `almalinux:10`, …) per role, run twice to check idempotency.
  The full `site.yml` does not run in a container (no systemd/grub).
- **VM** for Secure Boot/MOK and the full desktop.
- Never run on the host, not even with `--check`.

## Migration

1. **New repository `phguima/alpi`** (decided on 2026-10-05, instead of renaming AFPI). Code is
   ported from AFPI and AAPI step by step. The paths `host_vars/127.0.0.1.yml` (migrated to the
   directory) and `group_vars/all/secrets.yml` stay compatible.
2. **Restructure** around the three axes, the catalog, the `repos` role and `group_by`. Personal
   aliases go to `host_vars`.
3. **Fold in the AAPI deltas** as `os_AlmaLinux_10` (the work machine's choices go in its
   `selection.yml`). Carry both legacy
   `.zshrc` block cleanups (`NVIDIA AND API CONFIGURATION` and `API CONFIGURATION`).
4. **Prove parity** with the golden test + containers + VM.
5. **Freeze AAPI** with a README pointing to ALPI. The in-progress AFPI work (`noir` reinstall,
   step 8) finishes first, or is ported.
6. **Debian 13 / Ubuntu 26.04 LTS**: only once a test VM exists. Each one is a port of its own:
   `/var/run/reboot-required`, `update-grub`, Flatpak missing on Ubuntu, Firefox as a snap,
   extrepo/PPA, DKMS.

## Decisions (2026-10-05)

1. **Repository:** new empty `phguima/alpi`, public, GPL-3.0 (not a rename of AFPI). AFPI and AAPI
   stay active until parity.
2. **Uninstall:** yes, only through an explicit `packages_absent` list, without autoremove.
3. **Unknown catalog id:** fail early, in `env_setup`, listing every unknown id.
4. **Profile:** policy + package/feature sets; hardware stays detected and can only be vetoed.
   *Superseded on 2026-10-08: no profiles, see below.*
5. **VirtualBox:** fixed source per distro: RPM Fusion akmod + kmodgenca on Fedora, Oracle repo on
   EL. No user choice.
6. **Debian/Ubuntu:** after Fedora + AlmaLinux parity, and only with a test VM. Reserve the slots
   (support matrix, catalog columns) now; write no tasks for them yet.
7. **Desktops:** GNOME and KDE from the start (parity requires both).

## Decisions (2026-10-08)

1. **Profiles removed.** Deciding a machine's packages by a name chosen in advance (`personal`,
   `work`) does not fit: the choice belongs to the machine. They carried little (`work`: no
   hostname, no Steam). Replaced by:
   - the hostname: managed only when `bootstrap.sh` is given one (empty leaves it alone);
   - packages and features: `pick.py`, listing only what the running distro offers, saved as
     differences from the defaults in `host_vars/127.0.0.1/selection.yml`.
2. **Hardware vetoes stay in `custom.yml`**, not in the picker (no second detection).
3. A `bootstrap.yml` written before this keeps working: `alpi_profile` is ignored by the playbook
   and dropped by the next `bootstrap.sh`.

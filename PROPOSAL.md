# ALPI — Ansible Linux Post-Install

Architecture proposal (2026-10-05). Revised after an adversarial review.

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
2. **Hardware**: detected (NVIDIA, ASUS, AMD, Secure Boot). The profile or the user can **only
   veto** it (`nvidia: auto | false`).
3. **Machine/user**: lives in `host_vars`, outside git. The thevoid UUID leaves the repository and
   comes here.

The **profile** (`personal`, `work`) carries policy (hostname, hardware vetoes) and package/feature
sets (e.g. `work` skips steam and discord). It can never turn on hardware that was not detected.

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
    profile_personal/  profile_work/
  host_vars/127.0.0.1/      # git-ignored
    bootstrap.yml           # written by bootstrap (hostname, git identity)
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

- **Precedence:** do not use `include_vars` for distro/profile, because it has higher priority than
  `host_vars` and the profile would silently override the user. Instead, `group_by` creates dynamic
  groups (`os_<distro>`, `os_<distro>_<major>`, `profile_<name>`) and the data lives in
  `group_vars/`. That keeps `host_vars` and `-e` on top. Layers never share a key (each has its own
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
  brave-origin], repo: brave}`. Repositories are defined by id (`alpi_repos_common` in
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

### User file (outside git)

```yaml
# host_vars/127.0.0.1/custom.yml
features:      {virtualbox: false, clamav: false}
packages_add:  [vim, "rpm:sqlitebrowser", "flatpak:org.gimp.GIMP"]   # prefix = raw name, bypasses the catalog
packages_skip: [discord]
packages_absent: [akregator]   # explicit uninstall (see Removal)
```

### Rules

- **Merging:** each layer uses its own keys (`packages_base`, `packages_profile`, `packages_add`,
  `packages_skip`). A single `set_fact` builds the final list:
  `(base + profile + add) | unique | difference(skip)`. The user layer is applied last. Never use
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
- **Separate files:** bootstrap rewrites its own `bootstrap.yml` with PyYAML, which would wipe
  hand-written comments. That is why `custom.yml` is a separate file. Since both stay outside git,
  `git pull` never conflicts.
- **No interactive picker in bootstrap:** it would re-implement the catalog in bash.

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

### Traps in the current code to fix during migration

- The VirtualBox gate is a string match: `'VirtualBox' in dnf_packages_common`
  (`afpi/roles/apps/tasks/main.yml:25`).
- `clamav-freshclam` is enabled unconditionally: if ClamAV is skipped, the run breaks.
- The Bitwarden and Zoom Flatpak overrides run even when those apps are not installed.

Each of these becomes a feature or is guarded by the resolved package set.

## Tests

- **Golden test:** a play that only prints the resolved package, flatpak and feature sets for each
  (distro, profile, DE). The output is compared with what AFPI and AAPI install today. This is what
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
3. **Fold in the AAPI deltas** as `os_AlmaLinux_10` + the `work` profile. Carry both legacy
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
5. **VirtualBox:** fixed source per distro: RPM Fusion akmod + kmodgenca on Fedora, Oracle repo on
   EL. No user choice.
6. **Debian/Ubuntu:** after Fedora + AlmaLinux parity, and only with a test VM. Reserve the slots
   (support matrix, catalog columns) now; write no tasks for them yet.
7. **Desktops:** GNOME and KDE from the start (parity requires both).

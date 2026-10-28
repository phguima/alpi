# ALPI — instructions for Claude

ALPI (Ansible Linux Post-Install): unifies AFPI (`phguima/afpi`, Fedora, personal machine `noir`)
and AAPI (`phguima/aapi`, AlmaLinux 10, work machine) into one project that detects the distro.
Public repo `phguima/alpi`, single branch `main`, GPL-3.0. Talk to the user in English; all docs
are in English.

## Work status

Skeleton stage (created on 2026-10-05; skeleton done the same day). `PROPOSAL.md` holds the architecture (reviewed by an
adversarial agent); `TODO.md` holds the work plan (decisions are recorded in `PROPOSAL.md`).
**Read both before starting.** `TODO.md` lists open items only: when an item is done, move it to
`TODO-HISTORY.md` in the same commit (decided 2026-10-24: end of its section there, with the date,
a short summary and the commit, named by its title since a commit cannot contain its own hash;
what code relies on goes in this file), and remove a section from `TODO.md` once it is empty.
Record the validation in the commit message.

Decision of 2026-10-05: **new** repo, without AFPI's history. AFPI and AAPI stay active until
parity; code comes in step by step, ported from them. Changes made there in the meantime (e.g.
`flatpak_filesystem_overrides`) must be brought here.

## Layout (skeleton, 2026-10-05)

- `site.yml`: `tasks/env_setup.yml` (support matrix assert, `alpi_support`: `{min, max}` majors or
  an exact `{version}` → user/hardware/DE facts, ported from
  AFPI → `group_by` into `family_<os_family>`, `os_<distro>`, `os_<distro>_<major>` → machine-settings assert →
  `tasks/resolve.yml`), then the roles (`repos`, `update`, `boot`, `memory`, `akmods_mok`, `virtualbox`,
  `packages`, `upstream`, `common`, `zsh`, `desktop`, `pipx`, `ai_tools`, `clamav`, `asus`, `nvidia` so far),
  then `tasks/reminders.yml` in `post_tasks` (tag `reminders`, not `always`, so `--tags resolve`
  stays quiet): the `gh auth login` reminder when `gh` is selected and `~/.config/gh/hosts.yml`
  has no `github.com:` (sets `alpi_gh_login_needed`), and the disk swap reminder when
  `hibernate` is on and disk swap is smaller than RAM (`alpi_memory.hibernate_reminder`), then
  AAPI's final status banner (`alpi_final_status`; a run stopped by the reboot gate never gets
  there).
- apt settings for the whole play (`site.yml`'s `environment` and `module_defaults`, from
  `group_vars/family_Debian/apt.yml`, empty on dnf and before `group_by`): `apt_environment`
  (`DEBIAN_FRONTEND=noninteractive`, `NEEDRESTART_MODE=a`) and `apt_lock_timeout` (600 s for the
  apt module's dpkg lock wait, which `ansible.builtin.package` passes on: unattended-upgrades holds
  the lock on a fresh install). Scenarios that import roles without `site.yml` do not get them.
- `tasks/resolve.yml` + `filter_plugins/alpi.py`: catalog lookup, merge of the package/feature
  layers, all validation (fails before anything changes). Keep logic in the filter plugin, not in
  long Jinja expressions.
- `group_vars/all/{support,catalog,packages,features,repos,machine}.yml`, `group_vars/family_*/`
  (data a family's distros share: repository definitions, apt settings…), `group_vars/os_*/`: each layer has its
  own keys, so group order does not matter (`ansible_group_priority` does not work in
  `group_vars/`). `pick.py` loads the same layers (`FAMILIES` maps a distro to its family).
- No profiles (removed 2026-10-08, PROPOSAL "Decisions (2026-10-08)"). `host_vars/127.0.0.1/`
  (git-ignored): `bootstrap.yml` (written by `bootstrap.sh`: hostname, git identity),
  `selection.yml` (written by `pick.py`: `packages_selection_add/_skip`, `features_selection`,
  differences from the defaults) and `custom.yml` (the user's, see `custom.yml.example`, applied
  last). Files in one `host_vars` directory do not merge a shared key: never reuse a key across
  them.
- `pick.py`: the package picker (whiptail, or text prompts with `ALPI_PICKER=text`). Reads the
  catalog files and reuses `filter_plugins/alpi.py`, so it lists exactly what the playbook would
  resolve on the running distro/desktop; hardware features are not listed (vetoes in
  `custom.yml`). Groups by purpose and labels in `group_vars/all/picker.yml` (`picker_groups`,
  `picker_descriptions`): a new catalog id or feature goes in a group there with a description
  (a unit test fails otherwise). The zsh aliases (`zsh_aliases` + `zsh_aliases_family` + `zsh_aliases_os`) are the last
  group, "Shell aliases (zsh)", their commands rendered with jinja2 (`show_command`: the user's
  home as `~`, unknown names as `<name>`), saved as `zsh_aliases_selection`. `visible()`: an
  item is hidden while an id in its `requires` (aliases: zsh and their own) is listed and
  unchecked, keeping its check; the menu, the checklists and the text list (reprinted when the
  numbers change) show only visible items. Rows: description,
  then what it installs or the alias's command (`rows`; the description gets its width first,
  whiptail rows padded to fill the box, which is up to 160 columns wide). whiptail: menu of
  groups (its list as tall as its entries, or the text's second line disappears), a checklist
  per group, a review before saving; text mode: one numbered list with group headers, each group
  aligned on its own. Preview without whiptail on screen: a detached tmux on its own socket
  (`tmux -L <name>`, never the user's server) and `capture-pane -p`. Unit tests in
  `tests/unit/test_pick.py` (fake `/etc/os-release`; whiptail replaced by scripted answers).
- `roles/repos` (before `packages`): enables `alpi_repos_enabled` from `resolve.yml` (the distro's
  always-on repos, then the ones the selected catalog entries name with `repo:`). Repositories with
  `repo_gpgcheck` get `dnf -y makecache` so their metadata key is imported; otherwise every
  non-interactive dnf call fails on them.
  yum repository ids are the `.repo` file/section names: keep AFPI's and AAPI's (`brave-browser`,
  `code`, `gh-cli`, `virtualbox`), or a migrated machine gets each repository twice.
  Definitions per family (`alpi_repos_family` in `group_vars/family_<os_family>/repos.yml`) plus
  the distro's `alpi_repos_os`; `tasks/<os_family>.yml`. apt (`Debian.yml`): Debian's own
  `apt_components` added to its sources in either format (`alpi_apt_components`, only the
  release's suites, `cdrom:` lines left alone), then `deb822` repositories written under the
  vendor's own file name and keyring path (`file`, `keyring`; `.asc` keys dearmored): two files
  for one repository with different `Signed-By` make apt refuse every source. i386 multiarch
  (`dpkg --add-architecture`) when a selected id is in `apt_i386_ids` (Steam's 32-bit libraries,
  the NVIDIA driver's), never removed.
- `roles/packages`: name checks first (`check_<os_family>.yml`: dnf dry run with `--allowerasing`
  like the swaps, which fails outright when a repository's metadata cannot be read instead of
  reporting nothing, and on dependencies that do not resolve (`alpi_unresolved_native`: Problem
  lines with neither a transaction summary nor "Nothing to do", since dnf prints a Problem block
  even when it resolves around it); apt (`check_Debian.yml`): `apt-get update` run and read, since
  it exits 0 when a source cannot be fetched (`W: Failed to fetch`; retried while the lists lock is
  held, which `DPkg::Lock::Timeout` does not cover), then `apt-get install -s` of the whole set read
  by `alpi_apt_simulation` (every unknown name first, unmet dependencies only when none is
  missing); `flatpak remote-info`),
  then replacements (catalog `swap: true`, or per distro `{native: …, swap: true|false}`;
  installed with `allowerasing` where dnf is the package manager, apt replaces through package
  metadata: `ffmpeg`, `mesa-va-drivers-freeworld`), base, user extras, explicit uninstalls. Needs the `repos` role
  before it (section 2). Native names may be dnf groups (`@multimedia`).
- Flatpak overrides: `group_vars/all/flatpak.yml` (`flatpak_overrides_common`: ZapZap reads
  `~/wks`, every desktop; `flatpak_overrides_kde`: Bitwarden, Zoom) plus
  the user's `flatpak_overrides` and `flatpak_filesystem_overrides` (`custom.yml`), merged by
  `alpi_flatpak_overrides` in `resolve.yml` into `alpi_flatpak_overrides`, only for apps in the
  resolved Flatpak sets; applied at the end of `roles/packages` with `flatpak override --user`
  (`tasks/flatpak_overrides.yml`; changed only when the override file differs). Removing an
  entry does not undo it, except for the cedilla workaround's apps (`reset_if`, below).
- Cedilla on XWayland (ported from AAPI, 2026-10-13): under KWin 6.6, Chromium/Electron apps on
  native Wayland ignore `~/.XCompose`. `tasks/cedilla.yml` (from `resolve.yml`, and again at the
  end of `roles/update`, which may upgrade KWin) reads `kwin_version` (`rpm -q kwin`, or the upstream version of `kwin-wayland` from `dpkg-query` on Debian/Ubuntu; `alpi_cedilla_xwayland` drops a dpkg epoch and revision; KDE only;
  pinned by extra vars in tests) and sets `alpi_cedilla_xwayland` (`alpi_cedilla_xwayland`
  filter: `cedilla_xwayland` auto/true/false in `custom.yml`, auto = KWin older than
  `cedilla_xwayland_kwin_below`, KDE only) and the Flatpak overrides; when the second pass
  changes the decision it sets `alpi_cedilla_flipped` and asks for a new login (a new KWin needs
  a login, not a reboot). On: the
  `cedilla_flatpak_overrides` layer replaces `flatpak_overrides_kde` app by app; Brave/VS Code
  menu entries copied with `--ozone-platform=x11` (`roles/desktop/tasks/xwayland.yml`, plan from
  `alpi_xwayland_entries`: ALPI's copies carry a marker and are rebuilt on every run, AAPI's are
  recognized as the system entry plus the flag, a user's own copy only gets the flag); the flag
  in the Antigravity entry and the `antigravity-ide`/`code` aliases. Off: everything undone, and
  each cedilla app's override file that still grants `~/.XCompose` is reset before the other
  layers are applied again.
- `roles/update` (after `repos`, before anything that builds modules or installs packages):
  `dnf_config` into `/etc/dnf/dnf.conf` (replaced, not appended), full upgrade with `nobest`
  (RPM Fusion's freeworld builds pin their EPEL library's exact version; EL's `best=True` would
  fail the run until RPM Fusion rebuilds, so the library is held back instead), then the reboot
  gate: `dnf needs-restarting -r` rc 1, or the newest installed `kernel-core` is not the running
  kernel (noir's local-time RTC fools needs-restarting), ends the play for the host. Otherwise
  it ends with `tasks/cedilla.yml` again (the upgrade may bring a newer KWin). Per family
  (`RedHat.yml`, `Debian.yml`, each setting `alpi_reboot_needed` for the shared gate); apt:
  `upgrade: dist` (full-upgrade: new dependencies installed, replaced packages removed, as dnf
  does), reboot when `/run/reboot-required` exists (Ubuntu's flag; Debian writes none) or the
  newest installed `linux-image-<release>` is not `uname -r` (metapackages and `-unsigned` builds
  left out).
- `roles/boot` (after `update`): kernel maintenance (refuses to run on a debug kernel; removes
  debug kernels, disables enabled debug repositories (`debug_repos_dnf5.yml` / `_dnf4.yml` by
  `pkg_mgr`: dnf5's `config-manager setopt` writes `/etc/dnf/repos.override.d/`, not the .repo),
  removes installonly packages older than the newest, never the running kernel, with
  `allowerasing` for the akmods' kmods) and `grub_settings` into `/etc/default/grub` (skipped
  when it does not exist; `grub_settings_absent` removes dead keys, AFPI's `GRUB_GFXPAYLOAD`),
  handler `grub_regenerate` (`grub2-mkconfig -o /boot/grub2/grub.cfg`). On BLS (Fedora, EL) `10_linux` only emits
  `blscfg`: settings read by `linux_entry` (`GRUB_GFXPAYLOAD_LINUX`) do nothing there. Debian and
  Ubuntu (`group_vars/family_Debian/boot.yml`): no kernel maintenance (apt's autoremove keeps the
  running and newest kernels); the settings plus `grub_settings_family` (`GRUB_TIMEOUT_STYLE=menu`:
  Ubuntu's `hidden` skips the menu whatever the timeout) go to `grub_dropin`
  (`/etc/default/grub.d/99-alpi.cfg`, read after `/etc/default/grub` and the other drop-ins, where
  Ubuntu's packages put settings), handler `update-grub`.
- `roles/memory` (after `boot`; installs its own package): swap on zram through zram-generator
  (`group_vars/all/memory.yml`, PROPOSAL "Decisions (2026-10-14)"). Reads `swapon --show --raw
  --bytes`, zswap (`zram_zswap_param`), `zram_generator_query` (`rpm -q`, or `dpkg-query`'s
  status on apt, printing "installed") and
  `/etc/systemd/zram-generator.conf`; `alpi_zram_plan` decides on/off/skip and prints the swap
  summary. `zram: auto` skips (with a note) a zram device zram-generator did not make, the user's
  own `/etc` config (no `zram_marker`) and zswap on; `true`/`false` fail there instead. On:
  `zram_package` (`zram-generator-defaults`: Fedora's default, EL lacks it;
  `systemd-zram-generator` on Debian and Ubuntu, which ships the `[zram0]` file itself;
  `group_vars/family_*/memory.yml`), `zram_size` as the drop-in
  `zram-generator.conf.d/50-alpi.conf` (not `/etc/systemd/zram-generator.conf`, which replaces
  the vendor file), `/etc/sysctl.d/99-alpi-zram.conf` from `zram_sysctl`. Off: the package
  stays, a marker-only `/etc/systemd/zram-generator.conf` switches it off. Disk swap is never
  created or removed. Runtime steps (sysctl values, starting/stopping zram0) are tagged
  `zram_apply`.
- `roles/akmods_mok` (before `packages`): Secure Boot signing key + MOK enrollment request, only
  when Secure Boot is on, the distro's `kmod_signer` is one of `kmod_signers`
  (`group_vars/all/secureboot.yml`: `akmods` on Fedora for `nvidia-driver` and `virtualbox`,
  key from `kmodgenca -a`; `dkms` on Debian for `nvidia-driver`, key from `dkms generate_mok`
  (DKMS 3.2 would create it at the first build otherwise); `shim` on Ubuntu for both, key from
  `update-secureboot-policy --new-key` in `/var/lib/shim-signed/mok`, where Ubuntu's DKMS and
  Oracle's `vboxdrv.sh` both sign from, so `roles/virtualbox` finds it and one enrollment covers
  both; `none` on EL) and one of its ids was
  selected (the signer signs at build time, so the key must exist first). `mok_password` per distro (`fedora-alpi` in `group_vars/os_Fedora`,
  `alma-alpi` in `group_vars/os_AlmaLinux_10`, `debian-alpi` in `group_vars/os_Debian`, `ubuntu-alpi` in `group_vars/os_Ubuntu`; notes in `group_vars/all/secureboot.yml`). `tasks/enroll.yml`
  (MOK enrollment of one key) is shared with `roles/virtualbox`.
- `roles/virtualbox` (before `packages`; runs when the `virtualbox` id is selected, whatever the
  native names): on a non-akmod build (Oracle, EL and Debian) with Secure Boot, its
  own key in `/var/lib/shim-signed/mok` (vboxdrv.sh signs with it); `vboxusers`/`vboxsf` groups;
  `/etc/modprobe.d/alpi-kvm.conf` (`options kvm enable_virt_at_load=0`: since kernel 6.12 kvm
  holds VT-x/AMD-V from load and VirtualBox fails with `VERR_VMX_IN_VMX_ROOT_MODE`; VirtualBox
  7.2 shares VT-x with KVM only on kernels 6.16+, so Fedora on Intel does not need it, but EL10
  (6.12) and AMD hosts do; set on every distro), removed when VirtualBox is not selected.
- `roles/clamav` (after `packages`): enables `clamav-freshclam.service` only when the
  `clamav-freshclam` catalog id was resolved (feature on, not skipped). Gate service roles on the
  resolved ids, never on the feature flag alone.
- `alpi_ids_selected` (`resolve.yml`): catalog ids that will be installed (base + extra, minus
  unavailable). Roles gate their configuration on it (`clamav`, `asus`, `zsh`), never on a
  feature flag alone.
- `roles/zsh`: Oh My Zsh, theme (`files/kali-like-alt.zsh-theme`), plugins, login shell and the
  managed aliases block for `zsh_users` (root + the user); only when `zsh` is selected. Aliases
  are named definitions (decided 2026-10-25): `zsh_aliases` in `group_vars/all/zsh.yml` plus the
  family's `zsh_aliases_family` and the distro's `zsh_aliases_os`, a later layer winning a name
  (`full-update`, per distro on dnf and per family on apt, where it ends with `roles/update`'s
  reboot signals; it runs `zsh_full_update_tools`: each update in
  `zsh_full_update_cmds` (npm, claude, agy) whose command is in `PATH` when it runs), each
  `{cmd, description, root, requires}`. All on, unless switched off by name in
  `zsh_aliases_selection` (picker) or `zsh_aliases_enabled` (`custom.yml`, wins), merged into
  `alpi_zsh_aliases_on` and checked in `resolve.yml`; `alpi_zsh_aliases` writes
  `alias <name>='<cmd>'` for those whose `requires` (catalog id or feature) is installed or on,
  root's `.zshrc` only the `root: true` ones. An alias name must not be a catalog id or feature
  (unit test). The user also gets `zsh_aliases_cedilla` (VS Code on XWayland, not a choice) and
  the machine's `luks_volumes` + `zsh_aliases_custom` from `custom.yml`, joined in a
  double-quoted scalar: in a folded one (`>-`) `join('\n')` gets a literal backslash-n. Null layers
  are rejected before `trim`, which writes them as "None": since ansible-core 2.19 a template that
  outputs nothing (the cedilla layer when off) is None, as is an empty `custom.yml` key;
  `luks_volumes` and `zsh_aliases_custom` must otherwise be a mapping and a string (`env_setup`).
  `open-thevoid` / `close-thevoid` (noir's LUKS disk, `thevoid_uuid`) are ordinary `zsh_aliases`
  definitions, so the picker toggles them; `luks_volumes` is for a machine's other volumes. API keys block (`api_keys`, from the
  optional vault `group_vars/all/secrets.yml`; never defaulted in `group_vars/all/zsh.yml`, which
  loads after `secrets.yml` and would override it) in the user's `.zshrc` only, removed when
  empty; AFPI's legacy `NVIDIA AND API CONFIGURATION` block removed. `luks_volumes` is validated in
  `env_setup` (`alpi_invalid_luks`) and turned into aliases by `alpi_luks_aliases` (by-uuid).
- `roles/desktop` (after `zsh`; skipped when the user is root): `~/wks`, Konsole on KDE (profile
  and color scheme in `files/`, `konsolerc`), Ptyxis on GNOME (gsettings/dconf as the user, with
  `XDG_RUNTIME_DIR`/`DBUS_SESSION_BUS_ADDRESS` set from the user's uid; changed only when the
  read-back value differs; only when Ptyxis's schema is installed: Debian's GNOME has
  gnome-terminal), cedilla (`~/.XCompose` from the Compose file of the locale in
  `/etc/locale.conf` or Debian's and Ubuntu's `/etc/default/locale`, fallback `en_US.UTF-8`). Ansible runs modules with `LANG=C.utf8`, so
  `ansible_facts['env']['LANG']` never shows the session's locale (AFPI/AAPI's lookup found
  nothing because of that). Steam on the NVIDIA GPU: a launcher with `PrefersNonDefaultGPU` gets
  switcheroo-control's offload from the desktop (checked on noir, 2026-10-25). Fedora's own
  launcher has it; Debian's and Ubuntu's (steam-installer) do not, so with `steam_gpu_launcher`
  (`group_vars/family_Debian`) and Steam and the NVIDIA driver selected, `tasks/steam.yml`
  writes a user copy of the system launcher with `PrefersNonDefaultGPU` and
  `X-KDE-RunOnDiscreteGpu` and a marker, rebuilt on every run and removed otherwise
  (`alpi_steam_launcher`). A user `steam.desktop` carrying `env __NV_PRIME_RENDER_OFFLOAD=1`
  (ALPI's old one or AFPI's) goes or becomes that copy; any other one is the user's own.
  `nvidia_prime_env` (`group_vars/all/desktop.yml`) is the `nvidia-run` alias.
- `roles/asus` (after `packages`): `/etc/asusd` (`asusctl`), `supergfxd.service` (`supergfxctl`,
  tagged `supergfxd`), ROG Control Center autostart (`asusctl-rog-gui`), each gated on its
  resolved id (`asus_selected` in `vars/main.yml`).
- `roles/pipx` (after `desktop`, so `pipx ensurepath` finds the user's `.zshrc`): Python apps
  for the user from catalog values `{pipx: <PyPI spec>}` (extras allowed) or `pipx:<spec>` in
  `custom.yml`; `pipx_inject` and `pipx_playwright_browsers` (`group_vars/all/pipx.yml`) apply
  only to installed apps; `packages_absent` removes pipx apps too. Names are checked on PyPI in
  `roles/packages/tasks/check.yml` (`alpi_pipx_name` strips extras/specifiers). The test
  scenarios skip the three large apps (`catalog` checks them on PyPI) and install `pipx:cowsay`.
- `roles/ai_tools` (after `zsh`: the Antigravity CLI's shell setup edits `.zshrc`, which must
  already come from the Oh My Zsh template; skipped when the user is root): features without
  catalog packages, so gated on `alpi_feature` itself (no ids to gate on), `claude_code`, `antigravity_cli` (vendor installers piped to bash as the user
  with `HOME` set, `creates` the binary in `~/.local/bin`; the tools update themselves) and
  `antigravity_ide` (AppImage into `antigravity_ide_dir` only when missing, from the update
  manifest via `alpi_appimage_release`: base64 sha512 to hex; icon extracted with
  `--appimage-extract`, menu entry, handler `update-desktop-database` for `antigravity://`).
  Installs its own deps (`curl`, `fuse2_package`: `fuse-libs`, or `libfuse2t64` on apt,
  `desktop-file-utils`). Ubuntu (`ai_tools_apparmor_userns`): unprivileged user namespaces only
  for programs with an AppArmor profile granting `userns`, which Electron's sandbox needs: an
  unconfined profile with `userns,` (`/etc/apparmor.d/alpi-antigravity-ide`) attached to the
  binary in the AppImage's mount (`/tmp/.mount_antigr*/antigravity`), loaded with
  `apparmor_parser -r`, or only parsed (`-Q -K`) where the kernel has no AppArmor. URLs in
  `group_vars/all/ai_tools.yml`; the picker's labels come from
  `picker_descriptions` (`group_vars/all/picker.yml`). `tasks/check.yml` (run by `catalog`) checks the upstream URLs without
  downloading. The alias is `antigravity-ide` because `agy install` deletes `alias antigravity=`.
- `roles/upstream` (after `packages`): catalog values `{upstream: <source id>}` (Roboto on EL,
  `tea` and `forgejo-cli` everywhere: PROPOSAL "Decisions (2026-10-28)"), sources in
  `group_vars/all/upstream.yml` (`upstream_sources`, each with a `type` handled by
  `tasks/<type>.yml`; an undefined id stops the run in `resolve.yml`). Latest release on GitHub,
  Gitea or Forgejo (same API shape), asset by regex (`alpi_github_release`: asset + GitHub's
  `sha256:` digest for get_url, or `sha256:<url>` of the asset matching `checksum_asset`).
  `github_fonts`: the members matching `files` flat into `dest`, replaced wholesale when the tag
  differs from `<dest>/.version`. `release_binary`: one program into `dest` (`/usr/local/bin`,
  root 0755), unpacked by the asset's name (`.tar.gz`: its `member`; `.xz`: decompressed, with
  `xz_package` from `group_vars/family_*/main.yml`; else as is), the tag in
  `<upstream_version_dir>/<id>.version` (`/var/lib/alpi/upstream`), replaced when the tag differs
  or the program is gone. Forge unreachable keeps what is installed; `packages_absent` removes
  it. The release body is parsed whatever its Content-Type. Name check in
  `roles/packages/tasks/check.yml` (`alpi_upstream_missing`: a 404 or no matching asset or
  checksum asset fails, no answer only warns). Installed by root, so it runs for root-only runs
  too.
- Catalog values per distro may be `{native: …, repo: …}`: a repository only that distro needs
  (Oracle VirtualBox on EL). Catalog keys (`alpi_catalog_keys` per distro): Fedora
  `fedora, rpm, all`, EL `el10, el, rpm, all`, Debian 13 `debian13, debian, deb, all`, Ubuntu
  26.04 `ubuntu2604, ubuntu, deb, all` (both in the matrix; first releases after the VM
  checklist); `rpm` holds RPM names Fedora and EL share, `deb` those Debian and Ubuntu share,
  `all` only names that exist on all four (check a new `all:` name there). A new catalog id
  needs a value for each (or `deb`/`all`), or `debian13`/`ubuntu2604` stop on it. Ubuntu's
  NVIDIA branch is pinned in its `ubuntu2604` value (`nvidia-driver-NNN-open` with Canonical's
  signed `linux-modules-nvidia-NNN-open-generic`, which provide `nvidia-dkms-NNN-open`: nothing
  is built), bumped on purpose; a literal, since `pick.py` reads the catalog untemplated.
- `roles/nvidia` (after `packages`): power options in `nvidia_modprobe_conf`
  (`group_vars/family_*/main.yml`: `/etc/modprobe.d/nvidia.conf` on Fedora,
  `/etc/modprobe.d/alpi-nvidia.conf` on apt, where the packages bring their own modprobe files,
  Debian's `nvidia.conf` among them) for `nvidia_module` (`nvidia`; `nvidia-current` in
  `group_vars/os_Debian`, which renames it); when no module exists for the running kernel,
  akmods rebuild + `dracut`, or `dkms autoinstall` where `kmod_signer` is `dkms`. Runs only when
  the `nvidia-driver` id is selected (NVIDIA detected, Fedora, Debian or Ubuntu, not skipped).
- Hardware features (`alpi_hardware_features`: nvidia, asus, intel, amd) follow detection and can
  only be vetoed; their packages come from `feature_packages`.
- `roles/common`: hostname (only when `system_hostname` is set) and the git
  identity/defaults in the user's `~/.gitconfig` (`group_vars/all/machine.yml`, values from
  `bootstrap.yml`; validated in `env_setup.yml`).
- Golden test: `ansible-playbook site.yml --tags resolve` only resolves and prints the sets.

## Git

- Start with `git fetch` + `git pull --ff-only`: the user also commits from other machines.
- Commit and push **only when the user asks**. Commits in English, Conventional Commits with scope
  (`feat(apps): …`, `docs(todo): …`).
- One branch, `main` (the development line); releases are annotated `vX.Y.Z` tags on it, which
  real machines follow through `./update.sh` (newest `v*` tag by version; `./update.sh main` for
  the latest commits). Tag only after `tests/run.sh full` passes on that exact commit; VM tests
  are not required per release (yet). Minor version for features, patch for fixes. Tests of
  `update.sh`: `tests/unit/test_update_sh.py` (throwaway origin and clone in `tmp_path`).

## Tests — Molecule (mandatory)

- **Every change or new feature ships with tests in the same commit**: new Molecule scenarios or
  updates to the existing ones (and pytest unit tests for Python code such as filter plugins).
  When behavior changes, update the scenarios that cover it. A change without tests is not done.
- Driver: podman (`molecule-plugins[podman]`), installed with pipx on the host:
  `pipx install molecule && pipx inject molecule 'molecule-plugins[podman]' ansible-core pytest`
  (pytest: `tests/run.sh` runs the unit tests with the venv's Python).
  The Molecule controller runs on the host, but every playbook run targets the scenario's
  container, never the host: plays get their hosts from Molecule's inventory, not `localhost`.
- Layout: `molecule/<scenario>/` (`molecule.yml`, `converge.yml`, `verify.yml`), one scenario per
  distro or role as needed. Use systemd-enabled images (`command: /sbin/init`) where
  services are involved. `verify.yml` asserts the outcome (packages, files, settings), not only
  that the run did not fail.
- Run: `molecule test -s <scenario>` (create → converge → idempotence → verify → destroy). The
  idempotence step replaces the manual "run twice". Hardware-only checks (Secure Boot/MOK, real
  reboot) stay in the user's VM.
- ALPI setup (2026-10-05):
  - Run with `tests/run.sh quick` while working (no real installs, a few minutes), `tests/run.sh
    full` before a commit, `tests/run.sh apt` for the scenarios with a Debian or Ubuntu instance,
    or `tests/run.sh <scenario>…`: pytest first, then the scenarios
    `ALPI_JOBS` at a time (default 4, longest first; `ALPI_JOBS=1` for one at a time; a failure
    does not stop the rest), logs in `~/.cache/alpi-molecule/logs/`, timed summary. Scenarios run
    side by side because they share nothing: their own container names, dnf volumes and network
    namespaces (the stand-in servers on 127.0.0.1 do not clash); keep it that way (no host
    network, no fixed host ports, no shared files on the controller other than the per-spec
    collections cache). Speed-ups: pipelining (`config_options` in `.config/molecule/config.yml`:
    Molecule writes its own `ansible.cfg`, so the repo's is never read in the scenarios); each container has its own dnf cache volume (`alpi-dnf-<instance>`, `keepcache`,
    set in `shared/prepare.yml`); collections come from `~/.cache/alpi-molecule/collections`
    (`shared/collections.yml`, downloaded once on the controller) instead of Galaxy. Cleanup:
    `podman volume rm $(podman volume ls -q --filter name=alpi-dnf-); rm -rf ~/.cache/alpi-molecule`.
    Plain Molecule still works: `molecule test --all` / `molecule test -s <name>`. Unit tests:
    `~/.local/share/pipx/venvs/molecule/bin/python -m pytest -q tests/unit` (the `pytest` in
    `~/.local/bin` is an old broken pip install of the user's; leave it alone).
  - In this harness, pipe Molecule's output (`molecule … 2>&1 | cat`): Ansible refuses to run
    with non-blocking stdio.
  - Molecule runs the first `ansible-playbook` in `PATH`. `tests/run.sh` puts the pipx venv's own
    `ansible-core` (a Molecule dependency, 2.21 on 2026-10-08) first, so both machines test with
    the same controller; the system one is 2.20 on the Fedora personal machine and 2.16 on the
    AlmaLinux 10 work machine, whose dnf5 module cannot install by URL. Plain `molecule test`
    uses the system one. It needs `containers.podman` and `community.general` in
    `~/.ansible/collections` (`ansible-galaxy collection install containers.podman
    community.general -p ~/.ansible/collections --force`; the copies in Fedora's `ansible`
    package are not searched by the venv's ansible-core: without `community.general` every
    scenario fails at its syntax step).
  - `.config/molecule/config.yml` is the base config: podman driver, `ALPI_TARGET=all` (site.yml
    targets localhost without it; `molecule/shared/converge.yml` refuses to run if it is unset),
    filter/role paths, links to the repo's `group_vars/` and the scenario's `host_vars/` (links
    replace inline `host_vars`, so a scenario's settings under test go in
    `molecule/<scenario>/host_vars/<instance>.yml`).
  - Scenarios: `catalog` (Fedora + Alma: repos + every name checked, nothing installed; the full
    resolved sets, and the host's `family_`/`os_` groups, compared with reviewed golden values in
    its `host_vars/`, via `shared/verify_resolution.yml`. Update those when the catalog or package lists change, after
    reviewing the diff; also the AI tools' upstream URLs, `roles/ai_tools/tasks/check.yml`),
    `fedora44-personal`, `el10-work` (real installs, heaviest apps skipped;
    `shared/verify_installed.yml` checks everything resolved is installed; `el10-work` also
    resolves with EL10's own ansible-core 2.16 inside the container,
    `shared/verify_native_controller.yml`, and its `prepare.yml` writes AAPI's repository files
    first: each vendor base URL must end up in one file only; both keep their settings in a host_vars directory,
    `host_vars/<instance>/{custom,selection}.yml`, like a real machine, and check that both
    files' layers apply), `failures` (every validation must fail with its message,
    `shared/expect_failure.yml`; Fedora + Alma + Debian 13; a case's `upstream_sources` goes through
    set_fact, saved and restored; its `prepare.yml` builds a freeworld stand-in that cannot be
    installed, `shared/pinned_pair.yml` (a local apt repository with the same pair on Debian);
    the unreadable source on apt is an unreachable `.list`, and both package managers' messages
    start the same, so a case has one `expect`), `flags` (env_setup on Fedora 44 with the hardware flags as
    key=value extra vars, i.e. strings: `is_nvidia=true` turns NVIDIA on, `=false` keeps the
    others off), `debian13` (env_setup + resolution on Debian 13; golden values like `catalog`;
    `roles/repos`, then every name of the golden set checked with apt, nothing installed),
    `debian13-personal` (`site.yml` on Debian 13, skipping what `fedora44-personal` skips: real
    installs as in `fedora44-personal`, Steam with its i386 libraries; `prepare.yml` holds the dpkg lock
    for 150 s, which the apt module must wait out: with `apt_lock_timeout: 20` the converge fails),
    `ubuntu2604-personal` (the same on Ubuntu 26.04, with `debian13-personal`'s playbooks; both
    also resolve with the distro's own ansible-core, 2.19 and 2.20, through
    `shared/verify_native_controller.yml`, as `el10-work` does with 2.16),
    `ubuntu2604` (as `debian13`, with its playbooks: each instance's sources file, components and
    candidates in its host_vars), `unsupported` (Debian 12, Ubuntu 26.10), `upstream` (`roles/upstream` on
    AlmaLinux 10 against stand-in GitHub, Gitea and Forgejo releases served by `http.server` on
    127.0.0.1:8766: Roboto, tea (.xz + .sha256) and fj (.tar.gz) install v1, `side_effect.yml`
    publishes Roboto and tea v2, deletes fj and runs again (Molecule's side_effect step, added to
    the scenario's test_sequence): replaced, fj v1 back; forges unreachable keep v0,
    `packages_absent` removes them; the personal and work scenarios install the real releases), `bootstrap`
    (bootstrap.sh with scripted answers, picker in text mode, on Fedora 44, Debian 13 and Ubuntu 26.04; a Debian
    13 without sudo must stop before installing anything and print the `su -` command), `common` (env_setup +
    `roles/common` on `almalinux/10-init` with systemd: static hostname via hostnamectl, git),
    `secureboot` (env_setup + `akmods_mok`, `virtualbox`, `nvidia`, nothing downloaded; converge
    renames EL's VirtualBox and Fedora's NVIDIA native packages, so the roles must gate on ids; Secure Boot
    detected from a fake EFI variable mounted over `/sys/firmware`: Fedora with Secure Boot and
    NVIDIA vetoed, Fedora without (and VirtualBox off: a stale `alpi-kvm.conf` removed), EL with,
    Debian with (DKMS key and Oracle key both enrolled, NVIDIA options for `nvidia-current`, a
    stand-in for Debian's own `nvidia.conf` left alone), Ubuntu with (one shim-signed key,
    requested once for DKMS and VirtualBox); fake `mokutil` in `files/` (state per key), real
    `kmodgenca`/`dkms`/`update-secureboot-policy`/openssl),
    `services` (env_setup + service roles on `almalinux/10-init` with systemd; prepare installs
    the packages: freshclam enabled and running, and skipped cleanly when its id is skipped; on
    Debian 13 too, built from `shared/Dockerfile-systemd-apt.j2`, the systemd image for any apt
    instance that needs services: Debian and Ubuntu publish no init image),
    `asus` (env_setup + `roles/asus` on Fedora 44 with systemd, built from the scenario's
    `Dockerfile.j2` since Fedora has no init image; stand-in supergfxd unit and launcher in
    `prepare.yml`: everything selected, and supergfxctl + GUI skipped), `update` (repos +
    `roles/update`; wrappers in `/usr/local/bin` script needs-restarting's answer and the newest
    kernel per instance, the dnf one still running the real needs-restarting: no reboot, reboot
    by needs-restarting (EL), reboot by a newer kernel; each also has an installed freeworld
    stand-in pinned to its library while a newer library is available, `shared/pinned_pair.yml`:
    the upgrade holds the library back; Debian 13, group `apt`: a local repository offers 2.0 of
    an installed stand-in, which every instance upgrades, and a `dpkg-query` wrapper names the
    newest kernel: no reboot, reboot by `/run/reboot-required`, reboot by a newer kernel),
    `memory` (env_setup + `roles/memory` +
    `tasks/reminders.yml`, `zram_apply` skipped; a `swapon` wrapper and a zswap file script the
    swap state per instance: no swap, Fedora's zram0 with `zram_size`, zswap on, `zram: false`
    after a run, the user's own config; Debian 13, group `apt`: no swap, and `zram: false` after
    a run), `boot` (`roles/boot` on Fedora + Alma;
    stand-in installonly packages and a debug kernel built with rpmbuild into a local repository
    whose id has 'debug', `/etc/default/grub` and a logging `grub2-mkconfig`; Debian 13, group
    `apt`: the values grub-mkconfig would source from `/etc/default/grub` and `grub.d`, with an
    Ubuntu-style drop-in hiding the menu before ALPI's, and a logging `update-grub`), `user`
    (`roles/zsh` + `roles/desktop` + `roles/ai_tools` for a regular user `alpi`, so root and the user differ: aliases
    split (exact lists per container: an alias off in GNOME's selection, KDE's custom.yml overriding its
    selection both ways, `claudecli` gone where Claude Code is off), API keys block for alpi only, legacy `.zshrc` blocks removed from both; the converge play sets `environment:` SUDO_USER
    and XDG_CURRENT_DESKTOP, which fact gathering sees too, and becomes alpi through sudo; GNOME
    container with Ptyxis and a session bus started as alpi at `/run/user/1000/bus` and a pt_BR
    `/etc/locale.conf`; KDE container without one, for the fallback; AlmaLinux 10 container
    without a desktop; Debian 13 container (group `apt`) with GNOME but no Ptyxis, a pt_BR
    `/etc/default/locale`, apt's `full-update` (zsh must parse what it expands to), the AI tools'
    packages under Debian names; Ubuntu 26.04 container without a desktop, where the Antigravity
    IDE gets its AppArmor profile (parsed, the container's kernel has no AppArmor). Cedilla on XWayland on KDE: stand-in `kwin` RPMs (rpmbuild) 6.6.4
    installed, stand-in Brave/VS Code system entries (`files/xwayland/`, on every container),
    AAPI's leftovers, and `roles/packages/tasks/flatpak_overrides.yml` run alone (flatpak only
    there); `side_effect.yml` keeps the on-state in `/root/alpi-xwayland-on/` and publishes 6.7.5,
    which converge's stand-in for `roles/update` installs before `tasks/cedilla.yml` runs again:
    the same run must undo everything; verify checks both states. `roles/ai_tools` against stand-ins in `files/ai/` served by
    `python3 -m http.server` on 127.0.0.1:8765 in each container (prepare writes the manifest with
    the stand-in AppImage's real sha512; converge's play vars point the URLs there): every tool on
    GNOME and EL, the Antigravity CLI and IDE on KDE; each stand-in refuses root and logs its runs; `is_nvidia`
    pinned true: GNOME loses ALPI's old Steam launcher and gets the `nvidia-run` alias, KDE vetoes
    NVIDIA and loses AFPI's leftover launcher, EL keeps a user's own, Debian and Ubuntu turn the old
    launcher into ALPI's copy of steam-installer's (a stand-in) with the GPU keys; `tasks/reminders.yml`: gh logged in on GNOME, reminded on KDE,
    skipped on EL, the fact recorded in `/root/alpi-gh-login-needed` for verify). That recipe
    is the way to test any user-specific step (root and the user differ there).
  - `fedora44-personal` and `el10-work` have no systemd: they skip service roles by tag
    (`skip-tags: molecule-notest,notest,clamav,supergfxd,update,memory`; `memory` because a
    container sees the host's swap; setting skip-tags replaces
    Molecule's default, so its own tags are repeated). Add each new service task's tag there;
    tag the service step alone when the rest of the role can run without systemd (as in
    `roles/asus`), so the real packages still get checked there.
  - Hostname in a rootless container: the kernel (transient) hostname cannot be changed, and
    `CAP_SYS_ADMIN` breaks systemd (units fail with 243/CREDENTIALS). So `common` starts the
    container as `noir` with the image's empty `/etc/hostname` (`--no-hostname` in
    `extra_opts`) and checks the static hostname; the transient one is left to the VM.
  - Extra vars win over set_fact, so detected hardware is pinned with
    `provisioner.options.extra-vars`: all false in `.config/molecule/config.yml`. A scenario that
    sets its own `extra-vars` replaces that string, so it lists all four (`is_nvidia`, `is_asus`,
    `is_intel`, `is_amd`). Never let a scenario detect hardware: `lspci` in a rootless container
    sees the host's GPU once `pciutils` is installed.
  - Images are bare: `shared/prepare.yml` installs python3 and sudo; the podman connection runs
    `raw` without a shell (wrap in `sh -c`). Bare Fedora lacks the Python rpm bindings, so verify
    with `rpm -q --whatprovides` (`shared/verify_installed.yml`; `dpkg-query` status `ii` on
    apt), not `package_facts`.
  - A failure-case harness must be shown to fail on a case that should not fail before trusting it.
  - Verify plays share registered vars across plays, and a registered var beats a task's `vars:`:
    give each play's vars their own prefix (`_steam_…`) or a later assert reads an earlier
    play's result.
  - `failures` runs every case in one play, and `group_by` groups stay for the whole play.
  - Pass/fail is Molecule's exit code and the absence of `Executed: Failed` lines, **not** the
    `SCENARIO RECAP`: after a failed step Molecule runs cleanup and the recap can still say
    `failed=0` (a non-zero `missing=` is the hint). This hid an idempotence failure on
    2026-10-06. `tests/run.sh` checks both.
  - Expected noise in a green log (checked 2026-10-06, again 2026-10-24 with Molecule 26.10.0;
    no `DEPRECATION` warnings left):
    - `fatal:` / `[ERROR]: Task failed` lines in `failures`: each case fails on purpose and
      `shared/expect_failure.yml` asserts the message (a case that does not fail, or fails with
      another message, turns the scenario red).
    - `CRITICAL 'molecule/default/molecule.yml' glob failed`: there is no `default` scenario, so
      Molecule disables shared state and carries on.
    - `Another version of 'containers.podman' … was found`: Fedora's `ansible` package ships one
      under `/usr/lib/python3.*`, the one in `~/.ansible/collections` is used.
    - Recheck after a Molecule, `ansible-core` or Fedora `ansible` upgrade (tracked in `TODO.md`,
      "Maintenance"): the CRITICAL line may stop being harmless (Molecule could start requiring
      `default` or exit non-zero) and the `~/.ansible/collections` copy of `containers.podman`
      must stay the newer one (reinstall with `--force`); the log's version warning shows both.
- The manual podman recipes below remain for quick experiments.

## Tests — in a container or VM, never on the host

Nothing runs on the host (the user's personal machine), not reads, not `--check`. Validate in
podman (`registry.fedoraproject.org/fedora:44`, `docker.io/library/almalinux:10`, …), **twice**
(`changed=0` on the 2nd). On Fedora with SELinux, mount the repo with
`--security-opt label=disable` (no `:z`, so host files are not relabeled). The simulation recipes
(fake Secure Boot, fake `mokutil`, GNOME session via D-Bus) are in AFPI's and AAPI's `CLAUDE.md`.
Recipes that worked here:
- Long-running containers (`podman run -d --name … sleep infinity` + `podman exec`) so ansible-core
  and `community.general` (11.x on EL10's 2.16) are installed once. Copy the repo into a **fresh
  directory per run** (`cp -r /src /aN`): `rm -rf` inside `podman exec … bash -c` is blocked by
  Claude Code's safety check.
- Run with `ANSIBLE_BECOME_ASK_PASS=False … -e ansible_become=false`; scenarios go through
  `host_vars/127.0.0.1/custom.yml` written inside the copy.
- `bootstrap.sh` interactively: `printf "answers\n" | script -qec ./bootstrap.sh /dev/null`, with a
  pass-through `sudo` shim first in `PATH` (the real `sudo` swallows the piped answers).
- Plays that include `roles/packages` must run `roles/repos` first, or names from EPEL/RPM
  Fusion/vendor repositories fail the name check.

Hardware (Secure Boot/MOK, reboot) goes to the user's VM, step by step from `tests/vm-checklist.md`
(Fedora, AlmaLinux) or `tests/vm-checklist-apt.md` (Debian, Ubuntu); results arrive as screenshots in
`~/Pictures/Screenshots` (list the directory and take the newest ones).

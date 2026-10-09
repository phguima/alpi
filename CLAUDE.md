# ALPI — instructions for Claude

ALPI (Ansible Linux Post-Install): unifies AFPI (`phguima/afpi`, Fedora, personal machine `noir`)
and AAPI (`phguima/aapi`, AlmaLinux 10, work machine) into one project that detects the distro.
Public repo `phguima/alpi`, single branch `main`, GPL-3.0. Talk to the user in English; all docs
are in English.

## Work status

Skeleton stage (created on 2026-10-05; skeleton done the same day). `PROPOSAL.md` holds the architecture (reviewed by an
adversarial agent); `TODO.md` holds the work plan (decisions are recorded in `PROPOSAL.md`).
**Read both before starting.** When an item is done, tick it (`- [x]`) in `TODO.md` in the same
commit, naming that commit by its title (a commit cannot contain its own hash; older ticks carry
short hashes); remove a section only once all its items are ticked. Record the validation in
the commit message.

Decision of 2026-10-05: **new** repo, without AFPI's history. AFPI and AAPI stay active until
parity; code comes in step by step, ported from them. Changes made there in the meantime (e.g.
`flatpak_filesystem_overrides`) must be brought here.

## Layout (skeleton, 2026-10-05)

- `site.yml`: `tasks/env_setup.yml` (support matrix assert → user/hardware/DE facts, ported from
  AFPI → `group_by` into `os_<distro>`, `os_<distro>_<major>` → machine-settings assert →
  `tasks/resolve.yml`), then the roles (`repos`, `update`, `boot`,
  `akmods_mok`, `virtualbox`, `packages`, `common`, `zsh`, `clamav`, `asus`, `nvidia` so far).
- `tasks/resolve.yml` + `filter_plugins/alpi.py`: catalog lookup, merge of the package/feature
  layers, all validation (fails before anything changes). Keep logic in the filter plugin, not in
  long Jinja expressions.
- `group_vars/all/{support,catalog,packages,features,repos,machine}.yml`, `group_vars/os_*/`:
  each layer has its own keys, so group order does not matter (`ansible_group_priority` does not
  work in `group_vars/`).
- No profiles (removed 2026-10-08, PROPOSAL "Decisions (2026-10-08)"). `host_vars/127.0.0.1/`
  (git-ignored): `bootstrap.yml` (written by `bootstrap.sh`: hostname, git identity),
  `selection.yml` (written by `pick.py`: `packages_selection_add/_skip`, `features_selection`,
  differences from the defaults) and `custom.yml` (the user's, see `custom.yml.example`, applied
  last). Files in one `host_vars` directory do not merge a shared key: never reuse a key across
  them.
- `pick.py`: the package picker (whiptail, or text prompts with `ALPI_PICKER=text`). Reads the
  catalog files and reuses `filter_plugins/alpi.py`, so it lists exactly what the playbook would
  resolve on the running distro/desktop; hardware features are not listed (vetoes in
  `custom.yml`). Unit tests in `tests/unit/test_pick.py` (fake `/etc/os-release`).
- `roles/repos` (before `packages`): enables `alpi_repos_enabled` from `resolve.yml` (the distro's
  always-on repos, then the ones the selected catalog entries name with `repo:`). Repositories with
  `repo_gpgcheck` get `dnf -y makecache` so their metadata key is imported; otherwise every
  non-interactive dnf call fails on them.
- `roles/packages`: name checks first (`check_<os_family>.yml`: dnf dry run, which fails outright
  when a repository's metadata cannot be read instead of reporting nothing; `flatpak remote-info`),
  then replacements (catalog `swap: true`, installed with `allowerasing`: `ffmpeg`,
  `mesa-va-drivers-freeworld`), base, user extras, explicit uninstalls. Needs the `repos` role
  before it (section 2). Native names may be dnf groups (`@multimedia`).
- Flatpak overrides: `group_vars/all/flatpak.yml` (`flatpak_overrides_kde`: Bitwarden, Zoom) plus
  the user's `flatpak_overrides` and `flatpak_filesystem_overrides` (`custom.yml`), merged by
  `alpi_flatpak_overrides` in `resolve.yml` into `alpi_flatpak_overrides`, only for apps in the
  resolved Flatpak sets; applied at the end of `roles/packages` with `flatpak override --user`
  (changed only when the override file differs). Removing an entry does not undo it.
- `roles/update` (after `repos`, before anything that builds modules or installs packages):
  `dnf_config` into `/etc/dnf/dnf.conf` (replaced, not appended), full upgrade, then the reboot
  gate: `dnf needs-restarting -r` rc 1, or the newest installed `kernel-core` is not the running
  kernel (noir's local-time RTC fools needs-restarting), ends the play for the host.
- `roles/boot` (after `update`): kernel maintenance (refuses to run on a debug kernel; removes
  debug kernels, disables enabled debug repositories (`debug_repos_dnf5.yml` / `_dnf4.yml` by
  `pkg_mgr`: dnf5's `config-manager setopt` writes `/etc/dnf/repos.override.d/`, not the .repo),
  removes installonly packages older than the newest, never the running kernel, with
  `allowerasing` for the akmods' kmods) and `grub_settings` into `/etc/default/grub` (skipped
  when it does not exist), handler `grub2-mkconfig -o /boot/grub2/grub.cfg`.
- `roles/akmods_mok` (before `packages`): Secure Boot signing key + MOK enrollment request, only
  when Secure Boot is on and an `akmod-*` package was resolved (akmods signs at build time, so the
  key must exist first). `mok_password` in `group_vars/all/secureboot.yml`. `tasks/enroll.yml`
  (MOK enrollment of one key) is shared with `roles/virtualbox`.
- `roles/virtualbox` (before `packages`): on a non-akmod build (Oracle, EL) with Secure Boot, its
  own key in `/var/lib/shim-signed/mok` (vboxdrv.sh signs with it); `vboxusers`/`vboxsf` groups.
- `roles/clamav` (after `packages`): enables `clamav-freshclam.service` only when the
  `clamav-freshclam` catalog id was resolved (feature on, not skipped). Gate service roles on the
  resolved ids, never on the feature flag alone.
- `alpi_ids_selected` (`resolve.yml`): catalog ids that will be installed (base + extra, minus
  unavailable). Roles gate their configuration on it (`clamav`, `asus`, `zsh`), never on a
  feature flag alone.
- `roles/zsh`: Oh My Zsh, theme (`files/kali-like-alt.zsh-theme`), plugins, login shell and the
  managed aliases block for `zsh_users` (root + the user); only when `zsh` is selected. Alias
  layers in `group_vars/all/zsh.yml` (common for root; user, `zsh_aliases_os` per distro,
  `zsh_aliases_nvidia` when `nvidia-driver` is selected, and the machine's `luks_volumes` +
  `zsh_aliases_custom` from `custom.yml` for the user). API keys block (`api_keys`, from the
  optional vault `group_vars/all/secrets.yml`; never defaulted in `group_vars/all/zsh.yml`, which
  loads after `secrets.yml` and would override it) in the user's `.zshrc` only, removed when
  empty; AFPI's legacy `NVIDIA AND API CONFIGURATION` block removed. `luks_volumes` is validated in
  `env_setup` (`alpi_invalid_luks`) and turned into aliases by `alpi_luks_aliases` (by-uuid).
- `roles/desktop` (after `zsh`; skipped when the user is root): `~/wks`, Konsole on KDE (profile
  and color scheme in `files/`, `konsolerc`), Ptyxis on GNOME (gsettings/dconf as the user, with
  `XDG_RUNTIME_DIR`/`DBUS_SESSION_BUS_ADDRESS` set from the user's uid; changed only when the
  read-back value differs), cedilla (`~/.XCompose` from the Compose file of the locale in
  `/etc/locale.conf`, fallback `en_US.UTF-8`). Ansible runs modules with `LANG=C.utf8`, so
  `ansible_facts['env']['LANG']` never shows the session's locale (AFPI/AAPI's lookup found
  nothing because of that).
- `roles/asus` (after `packages`): `/etc/asusd` (`asusctl`), `supergfxd.service` (`supergfxctl`,
  tagged `supergfxd`), ROG Control Center autostart (`asusctl-rog-gui`), each gated on its
  resolved id (`asus_selected` in `vars/main.yml`).
- `roles/pipx` (after `desktop`, so `pipx ensurepath` finds the user's `.zshrc`): Python apps
  for the user from catalog values `{pipx: <PyPI spec>}` (extras allowed) or `pipx:<spec>` in
  `custom.yml`; `pipx_inject` and `pipx_playwright_browsers` (`group_vars/all/pipx.yml`) apply
  only to installed apps; `packages_absent` removes pipx apps too. Names are checked on PyPI in
  `roles/packages/tasks/check.yml` (`alpi_pipx_name` strips extras/specifiers). The test
  scenarios skip the three large apps (`catalog` checks them on PyPI) and install `pipx:cowsay`.
- Catalog values per distro may be `{native: …, repo: …}`: a repository only that distro needs
  (Oracle VirtualBox on EL).
- `roles/nvidia` (after `packages`): `/etc/modprobe.d/nvidia.conf`; akmods rebuild + `dracut` only
  when no module exists for the running kernel. Runs only when `akmod-nvidia` was resolved
  (NVIDIA detected, Fedora, not skipped).
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

## Tests — Molecule (mandatory)

- **Every change or new feature ships with tests in the same commit**: new Molecule scenarios or
  updates to the existing ones (and pytest unit tests for Python code such as filter plugins).
  When behavior changes, update the scenarios that cover it. A change without tests is not done.
- Driver: podman (`molecule-plugins[podman]`), installed with pipx on the host:
  `pipx install molecule && pipx inject molecule 'molecule-plugins[podman]' ansible-core`.
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
    full` before a commit, or `tests/run.sh <scenario>…`: pytest first, then one scenario at a
    time (a failure does not stop the rest), logs in `~/.cache/alpi-molecule/logs/`, timed summary.
    Speed-ups: each container has its own dnf cache volume (`alpi-dnf-<instance>`, `keepcache`,
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
    uses the system one. It needs `containers.podman` in
    `~/.ansible/collections` (`ansible-galaxy collection install containers.podman -p
    ~/.ansible/collections --force`; the copy in Fedora's `ansible` package is not searched).
  - `.config/molecule/config.yml` is the base config: podman driver, `ALPI_TARGET=all` (site.yml
    targets localhost without it; `molecule/shared/converge.yml` refuses to run if it is unset),
    filter/role paths, links to the repo's `group_vars/` and the scenario's `host_vars/` (links
    replace inline `host_vars`, so a scenario's settings under test go in
    `molecule/<scenario>/host_vars/<instance>.yml`).
  - Scenarios: `catalog` (Fedora + Alma: repos + every name checked, nothing installed; the full
    resolved sets compared with reviewed golden values in its `host_vars/`, via
    `shared/verify_resolution.yml`. Update those when the catalog or package lists change, after
    reviewing the diff), `fedora44-personal`, `el10-work` (real installs, heaviest apps skipped;
    `shared/verify_installed.yml` checks everything resolved is installed; `el10-work` also
    resolves with EL10's own ansible-core 2.16 inside the container,
    `shared/verify_native_controller.yml`; both keep their settings in a host_vars directory,
    `host_vars/<instance>/{custom,selection}.yml`, like a real machine, and check that both
    files' layers apply), `failures` (every validation must fail with its message,
    `shared/expect_failure.yml`; Fedora + Alma), `unsupported` (Debian 13), `bootstrap`
    (bootstrap.sh with scripted answers, picker in text mode), `common` (env_setup +
    `roles/common` on `almalinux/10-init` with systemd: static hostname via hostnamectl, git),
    `secureboot` (env_setup + `akmods_mok`, `virtualbox`, `nvidia`, nothing downloaded; Secure Boot
    detected from a fake EFI variable mounted over `/sys/firmware`: Fedora with Secure Boot and
    NVIDIA vetoed, Fedora without, EL with; fake `mokutil` in `files/`, real `kmodgenca`/openssl),
    `services` (env_setup + service roles on `almalinux/10-init` with systemd; prepare installs
    the packages: freshclam enabled and running, and skipped cleanly when its id is skipped),
    `asus` (env_setup + `roles/asus` on Fedora 44 with systemd, built from the scenario's
    `Dockerfile.j2` since Fedora has no init image; stand-in supergfxd unit and launcher in
    `prepare.yml`: everything selected, and supergfxctl + GUI skipped), `update` (repos +
    `roles/update`; wrappers in `/usr/local/bin` script needs-restarting's answer and the newest
    kernel per instance, the dnf one still running the real needs-restarting: no reboot, reboot
    by needs-restarting (EL), reboot by a newer kernel), `boot` (`roles/boot` on Fedora + Alma;
    stand-in installonly packages and a debug kernel built with rpmbuild into a local repository
    whose id has 'debug', `/etc/default/grub` and a logging `grub2-mkconfig`), `user`
    (`roles/zsh` + `roles/desktop` for a regular user `alpi`, so root and the user differ: aliases
    split, API keys block for alpi only, legacy `.zshrc` blocks removed from both; the converge play sets `environment:` SUDO_USER
    and XDG_CURRENT_DESKTOP, which fact gathering sees too, and becomes alpi through sudo; GNOME
    container with Ptyxis and a session bus started as alpi at `/run/user/1000/bus` and a pt_BR
    `/etc/locale.conf`; KDE container without one, for the fallback). That recipe is the way to
    test any user-specific step (root and the user differ there).
  - `fedora44-personal` and `el10-work` have no systemd: they skip service roles by tag
    (`skip-tags: molecule-notest,notest,clamav,supergfxd,update`; setting skip-tags replaces
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
    with `rpm -q --whatprovides` (`shared/verify_installed.yml`), not `package_facts`.
  - A failure-case harness must be shown to fail on a case that should not fail before trusting it.
  - `failures` runs every case in one play, and `group_by` groups stay for the whole play.
  - Pass/fail is Molecule's exit code and the absence of `Executed: Failed` lines, **not** the
    `SCENARIO RECAP`: after a failed step Molecule runs cleanup and the recap can still say
    `failed=0` (a non-zero `missing=` is the hint). This hid an idempotence failure on
    2026-10-06. `tests/run.sh` checks both.
  - Expected noise in a green log (checked 2026-10-06):
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

Hardware (Secure Boot/MOK, reboot) goes to the user's VM; results arrive as screenshots in
`~/Pictures/Screenshots` (list the directory and take the newest ones).

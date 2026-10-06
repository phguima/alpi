# ALPI — instructions for Claude

ALPI (Ansible Linux Post-Install): unifies AFPI (`phguima/afpi`, Fedora, personal machine `noir`)
and AAPI (`phguima/aapi`, AlmaLinux 10, work machine) into one project that detects the distro.
Public repo `phguima/alpi`, single branch `main`, GPL-3.0. Talk to the user in English; all docs
are in English.

## Work status

Skeleton stage (created on 2026-10-05; skeleton done the same day). `PROPOSAL.md` holds the architecture (reviewed by an
adversarial agent); `TODO.md` holds **only what is left** (decisions are recorded in `PROPOSAL.md`).
**Read both before starting.** When an item is done, remove it from `TODO.md` and record the
validation in the commit message.

Decision of 2026-10-05: **new** repo, without AFPI's history. AFPI and AAPI stay active until
parity; code comes in step by step, ported from them. Changes made there in the meantime (e.g.
`flatpak_filesystem_overrides`) must be brought here.

## Layout (skeleton, 2026-10-05)

- `site.yml`: `tasks/env_setup.yml` (support matrix assert → profile assert → user/hardware/DE
  facts, ported from AFPI → `group_by` into `os_<distro>`, `os_<distro>_<major>`,
  `profile_<name>` → machine-settings assert → `tasks/resolve.yml`), then the roles (`repos`,
  `akmods_mok`, `packages`, `common`, `nvidia` so far).
- `tasks/resolve.yml` + `filter_plugins/alpi.py`: catalog lookup, merge of the package/feature
  layers, all validation (fails before anything changes). Keep logic in the filter plugin, not in
  long Jinja expressions.
- `group_vars/all/{support,catalog,packages,features,repos,machine}.yml`, `group_vars/os_*/`,
  `group_vars/profile_*/`: each layer has its own keys, so group order does not matter
  (`ansible_group_priority` does not work in `group_vars/`).
- `host_vars/127.0.0.1/bootstrap.yml` (written by `bootstrap.sh`: `alpi_profile`, hostname, git
  identity) and `custom.yml` (the user's, see `custom.yml.example`), both git-ignored.
- `roles/repos` (before `packages`): enables `alpi_repos_enabled` from `resolve.yml` (the distro's
  always-on repos, then the ones the selected catalog entries name with `repo:`).
- `roles/packages`: name checks first (`check_<os_family>.yml`: dnf dry run; `flatpak remote-info`),
  then replacements (catalog `swap: true`, installed with `allowerasing`: `ffmpeg`,
  `mesa-va-drivers-freeworld`), base, user extras, explicit uninstalls. Needs the `repos` role
  before it (section 2). Native names may be dnf groups (`@multimedia`).
- `roles/akmods_mok` (before `packages`): Secure Boot signing key + MOK enrollment request, only
  when Secure Boot is on and an `akmod-*` package was resolved (akmods signs at build time, so the
  key must exist first). `mok_password` in `group_vars/all/secureboot.yml`.
- `roles/nvidia` (after `packages`): `/etc/modprobe.d/nvidia.conf`; akmods rebuild + `dracut` only
  when no module exists for the running kernel. Runs only when `akmod-nvidia` was resolved
  (NVIDIA detected, Fedora, not skipped).
- Hardware features (`alpi_hardware_features`: nvidia, asus, intel, amd) follow detection and can
  only be vetoed; their packages come from `feature_packages`.
- `roles/common`: hostname (only when the profile sets `alpi_manage_hostname`) and the git
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
  distro/profile or role as needed. Use systemd-enabled images (`command: /sbin/init`) where
  services are involved. `verify.yml` asserts the outcome (packages, files, settings), not only
  that the run did not fail.
- Run: `molecule test -s <scenario>` (create → converge → idempotence → verify → destroy). The
  idempotence step replaces the manual "run twice". Hardware-only checks (Secure Boot/MOK, real
  reboot) stay in the user's VM.
- ALPI setup (2026-10-05):
  - Run everything: `molecule test --all`; one scenario: `molecule test -s <name>`. Unit tests:
    `~/.local/share/pipx/venvs/molecule/bin/python -m pytest -q tests/unit` (the `pytest` in
    `~/.local/bin` is an old broken pip install of the user's; leave it alone).
  - In this harness, pipe Molecule's output (`molecule … 2>&1 | cat`): Ansible refuses to run
    with non-blocking stdio.
  - Molecule uses the host's `ansible-core` (`/usr/bin`, 2.20) and needs `containers.podman` in
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
    `shared/verify_native_controller.yml`), `failures` (every validation
    must fail with its message, `shared/expect_failure.yml`; Fedora + Alma), `unsupported`
    (Debian 13), `bootstrap` (bootstrap.sh with scripted answers), `common` (env_setup +
    `roles/common` on `almalinux/10-init` with systemd: static hostname via hostnamectl, git),
    `nvidia` (env_setup + `akmods_mok` + `nvidia`, no driver download; Secure Boot detected from a
    fake EFI variable mounted over `/sys/firmware` on one container, absent on the other; fake
    `mokutil` in `files/`, real `kmodgenca`).
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
  - `failures` runs every case in one play, and `group_by` groups stay for the whole play: a case
    that depends on profile group_vars must come before cases that join another profile group
    (with two profile groups the alphabetically last one wins, e.g. `profile_work`).
  - Expected noise in a green `molecule test --all` log (checked 2026-10-06); only the
    `SCENARIO RECAP` decides pass/fail:
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

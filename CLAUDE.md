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
  `profile_<name>` → `tasks/resolve.yml`), then the roles (today only `packages`).
- `tasks/resolve.yml` + `filter_plugins/alpi.py`: catalog lookup, merge of the package/feature
  layers, all validation (fails before anything changes). Keep logic in the filter plugin, not in
  long Jinja expressions.
- `group_vars/all/{support,catalog,packages,features}.yml`, `group_vars/os_*/`,
  `group_vars/profile_*/`: each layer has its own keys, so group order does not matter
  (`ansible_group_priority` does not work in `group_vars/`).
- `host_vars/127.0.0.1/bootstrap.yml` (written by `bootstrap.sh`: `alpi_profile`, hostname, git
  identity) and `custom.yml` (the user's, see `custom.yml.example`), both git-ignored.
- `roles/packages`: name checks first (`check_<os_family>.yml`: dnf dry run; `flatpak remote-info`),
  then base, user extras, explicit uninstalls. Needs the `repos` role before it (section 2).
- Golden test: `ansible-playbook site.yml --tags resolve` only resolves and prints the sets.

## Git

- Start with `git fetch` + `git pull --ff-only`: the user also commits from other machines.
- Commit and push **only when the user asks**. Commits in English, Conventional Commits with scope
  (`feat(apps): …`, `docs(todo): …`).

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
- Without the `repos` role, EPEL/RPM Fusion packages (htop, ShellCheck, 7zip on EL10; steam,
  telegram on Fedora) must be skipped in full runs.

Hardware (Secure Boot/MOK, reboot) goes to the user's VM; results arrive as screenshots in
`~/Pictures/Screenshots` (list the directory and take the newest ones).

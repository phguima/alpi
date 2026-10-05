# ALPI — instructions for Claude

ALPI (Ansible Linux Post-Install): unifies AFPI (`phguima/afpi`, Fedora, personal machine `noir`)
and AAPI (`phguima/aapi`, AlmaLinux 10, work machine) into one project that detects the distro.
Public repo `phguima/alpi`, single branch `main`, GPL-3.0. Talk to the user in English; all docs
are in English.

## Work status

Design stage (created on 2026-10-05). `PROPOSAL.md` holds the architecture (reviewed by an
adversarial agent); `TODO.md` holds **only what is left**, starting with the open decisions.
**Read both before starting.** When an item is done, remove it from `TODO.md` and record the
validation in the commit message.

Decision of 2026-10-05: **new** repo, without AFPI's history. AFPI and AAPI stay active until
parity; code comes in step by step, ported from them. Changes made there in the meantime (e.g.
`flatpak_filesystem_overrides`) must be brought here.

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
Hardware (Secure Boot/MOK, reboot) goes to the user's VM; results arrive as screenshots in
`~/Pictures/Screenshots` (list the directory and take the newest ones).

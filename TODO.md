# TODO — ALPI

Work plan: open items only. A done item moves to `TODO-HISTORY.md` (date, short summary, commit)
in the commit that finishes it; a section goes once it is empty. Architecture, rationale and
decisions in `PROPOSAL.md`. Every item ships with its Molecule scenarios / unit tests (see
`CLAUDE.md`).

## 4. Parity

- [ ] On noir: does Steam run on the NVIDIA GPU from its own launcher (`PrefersNonDefaultGPU`,
      `X-KDE-RunOnDiscreteGpu`, via switcheroo-control) without ALPI's user launcher
      (`feat(desktop): …`)? If so, drop the override.

## 5. New distros (after parity, only with a test VM)

- [ ] Debian 13.
- [ ] Ubuntu 26.04 LTS.

## Maintenance

- [ ] After upgrading Molecule (and with it the venv's `ansible-core`, which `tests/run.sh`
      puts first in `PATH`) or Fedora's `ansible` package, rerun `tests/run.sh full` and recheck
      the expected log noise listed in `CLAUDE.md` (Molecule section): the `molecule/default`
      CRITICAL must still be non-fatal, the `containers.podman` in `~/.ansible/collections`
      must still be newer than the system copy, and the logs must have no `DEPRECATION`. Versions
      in the last green run, 2026-10-24 (AlmaLinux 10 work machine): Molecule 26.10.0 (host pipx),
      ansible-core 2.21.5 (Molecule's venv), `containers.podman` 1.21.1 and `community.general`
      11.4.9 (user; no system copy there). On 2026-10-06 (Fedora): ansible-core 2.20.7 (system),
      `containers.podman` 1.21.0 (user) vs 1.20.2 (system).

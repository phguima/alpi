# TODO — ALPI

Work plan: open items only. A done item moves to `TODO-HISTORY.md` (date, short summary, commit)
in the commit that finishes it; a section goes once it is empty. Architecture, rationale and
decisions in `PROPOSAL.md`. Every item ships with its Molecule scenarios / unit tests (see
`CLAUDE.md`).

## 5. New distros (after parity, only with a test VM)

Debian 13, then Ubuntu 26.04 LTS as a delta. Decisions, targets and checked facts in `PROPOSAL.md`
("Decisions (2026-10-24)"). Facts marked *(check)* are not confirmed yet: check them in a
container or VM before code relies on them. Consequences to keep in mind:
- The cedilla XWayland workaround turns on for both KDEs (KWin < 6.7).
- Debian's 6.12 kernel needs `/etc/modprobe.d/alpi-kvm.conf` (VirtualBox 7.2 shares VT-x with
  KVM only on 6.16+); on Ubuntu's 7.0 it is insurance, as on Fedora.
- Ubuntu's major version (`26`) is the same for 26.04 and 26.10: its support entry compares the
  full `distribution_version`.
- More controller lines: Debian's ansible-core 2.19 and Ubuntu's 2.20 (Data Tagging) next to
  EL10's 2.16 and Molecule's 2.21; `debian13-personal` and `ubuntu2604-personal` resolve with the
  container's own ansible-core, as `el10-work` does (`shared/verify_native_controller.yml`).

### Phase 5 — tests and release

- [ ] **VM checklist:** run `tests/vm-checklist-apt.md` on Debian 13 GNOME and KDE, Ubuntu 26.04
      and Kubuntu 26.04 (EFI + Secure Boot) and send the results: what containers cannot check
      (MOK enrollment and signed modules, `update-grub` and the menu, the reboot gate, the
      unattended-upgrades lock, the installer's own `sources.list`, cedilla and terminals in a
      session, the Antigravity IDE under AppArmor, `bootstrap.sh` without sudo). Fix what fails.
- [ ] **Steam on a hybrid NVIDIA laptop (Debian, Ubuntu):** ALPI's launcher copy with
      `PrefersNonDefaultGPU` (steam-installer's has none) starts Steam on the NVIDIA GPU: check on
      real hardware (`nvidia-smi` lists Steam) with Debian's 550 and Ubuntu's 615 drivers; drop the
      copy if switcheroo's offload does not work there.
- [ ] **Release:** after `tests/run.sh full` and the VM checklist per distro: Debian 13 as `v1.3.0`,
      Ubuntu 26.04 as `v1.4.0` (or one release if both land together), the tag message saying
      they are VM-checked (`v1.2.0` shipped them as a preview, decided 2026-10-25).

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

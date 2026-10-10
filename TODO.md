# TODO — ALPI

Work plan. Done items are ticked (with the commit); a section is removed once all its items are
ticked. Architecture, rationale and decisions in `PROPOSAL.md`. Every item ships with its Molecule
scenarios / unit tests (see `CLAUDE.md`).

## 4. Parity

- [ ] Golden test: resolved sets per (distro, DE) compared with AFPI and AAPI.
- [ ] `fedora:44` and `almalinux:10` containers, twice (idempotency).
- [ ] VM with EFI + Secure Boot, steps in `tests/vm-checklist.md` (also: the transient hostname, which containers cannot change; the
      NVIDIA akmod build, `dracut` and MOK enrollment, which containers only fake; `e` on a GRUB
      entry shows `set gfxpayload=keep` without `GRUB_GFXPAYLOAD`).
- [ ] On noir: does Steam run on the NVIDIA GPU from its own launcher (`PrefersNonDefaultGPU`,
      `X-KDE-RunOnDiscreteGpu`, via switcheroo-control) without ALPI's user launcher
      (`feat(desktop): …`)? If so, drop the override.
- [ ] Freeze AAPI and AFPI with a README pointing to ALPI.

## 5. New distros (after parity, only with a test VM)

- [ ] Debian 13.
- [ ] Ubuntu 26.04 LTS.

## Maintenance

- [ ] After upgrading Molecule (and with it the venv's `ansible-core`, which `tests/run.sh`
      puts first in `PATH`) or Fedora's `ansible` package, rerun `tests/run.sh full` and recheck
      the expected log noise listed in `CLAUDE.md` (Molecule section): the `molecule/default`
      CRITICAL must still be non-fatal, and the `containers.podman` in `~/.ansible/collections`
      must still be newer than the system copy. Versions in the green 2026-10-08 run (AlmaLinux 10
      work machine): Molecule 26.9.0 (host pipx), ansible-core 2.21.5 (Molecule's venv),
      `containers.podman` 1.21.1 (user; no system copy there). On 2026-10-06 (Fedora): ansible-core
      2.20.7 (system), `containers.podman` 1.21.0 (user) vs 1.20.2 (system).
- [ ] VLC and HEIF/HEVC freeworld codecs on EL (`vlc-plugins-freeworld`, `libheif-freeworld`,
      carried over from AAPI's TODO): left out because RPM Fusion builds them against newer
      libraries than stable EPEL ships. On 2026-10-04 both only waited for stable EPEL (it had
      `vlc-libs` 3.0.23 and `libheif` 1.17.6; `epel-testing` had 3.0.24 and 1.23.5, which both
      require). Do not enable `epel-testing`; once stable has them, add both to the catalog (`el`)
      and `packages_base`. Re-check with CRB, EPEL and RPM Fusion enabled:
      `dnf repoquery --qf "%{name}-%{version}" vlc-libs libheif` vs
      `dnf repoquery --requires vlc-plugins-freeworld libheif-freeworld | grep -E "^(vlc-libs|libheif)"`.

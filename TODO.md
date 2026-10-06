# TODO — ALPI

Work plan. Done items are ticked (with the commit); a section is removed once all its items are
ticked. Architecture, rationale and decisions in `PROPOSAL.md`. Every item ships with its Molecule
scenarios / unit tests (see `CLAUDE.md`).

## 2. Bring in AFPI (Fedora, `personal` profile)

- [ ] Port AFPI's roles and lists:
  - [x] Repositories: RPM Fusion, Brave, VS Code, GitHub CLI, ASUS COPR (`c952aff`).
  - [x] Application lists: DNF common/KDE/GNOME, Flatpaks, ClamAV and Steam as features
        (`0649a6a`, validated in `9080809`).
  - [x] Fonts, codecs (ffmpeg swap, @multimedia on Fedora), Intel/AMD video acceleration
        (`5b24977`).
  - [x] NVIDIA driver + `akmods_mok` (`56afb1b`).
  - [ ] VirtualBox as a feature (Fedora: `akmod-VirtualBox`, which `akmods_mok` picks up by
        itself).
- [x] Apply `system_hostname` (only when the profile has `alpi_manage_hostname`) and the git
      identity (`8d90381`).
- [ ] ASUS feature tasks beyond the packages (`/etc/asusd`, `supergfxd.service`, ROG GUI
      autostart). Needs systemd in Molecule: `common` uses `almalinux/10-init`, but the ASUS
      packages are Fedora only, so a Fedora image with systemd is still needed.
- [ ] Personal aliases (`open/close-thevoid`, LUKS UUID) to `host_vars`.
- [ ] Feature gates: VirtualBox (string match today), ClamAV (unconditional freshclam), Flatpak overrides only for installed apps.
- [ ] `flatpak_filesystem_overrides` empty in the repo, ZapZap in `custom.yml.example`.

## 3. Bring in AAPI (AlmaLinux 10, `work` profile)

- [ ] `group_vars/os_AlmaLinux_10` + `tasks/RedHat.yml` (dnf4, CRB/EPEL, Oracle VirtualBox).
- [ ] Cleanup of both legacy `.zshrc` blocks.

## 4. Parity

- [ ] Golden test: resolved sets per (distro, profile, DE) compared with AFPI and AAPI.
- [ ] `fedora:44` and `almalinux:10` containers, twice (idempotency).
- [ ] VM with EFI + Secure Boot (also: the transient hostname, which containers cannot change; the
      NVIDIA akmod build, `dracut` and MOK enrollment, which containers only fake).
- [ ] Freeze AAPI and AFPI with a README pointing to ALPI.

## 5. New distros (after parity, only with a test VM)

- [ ] Debian 13.
- [ ] Ubuntu 26.04 LTS.

## Maintenance

- [ ] After upgrading Molecule, `ansible-core` or Fedora's `ansible` package, rerun
      `molecule test --all` and recheck the expected log noise listed in `CLAUDE.md` (Molecule
      section): the `molecule/default` CRITICAL must still be non-fatal, and the
      `containers.podman` in `~/.ansible/collections` must still be newer than the system copy.
      Versions in the green 2026-10-06 run: Molecule 26.9.0 (host pipx), ansible-core 2.20.7,
      `containers.podman` 1.21.0 (user) vs 1.20.2 (system).

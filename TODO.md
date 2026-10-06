# TODO — ALPI

Only what is left. Architecture, rationale and decisions in `PROPOSAL.md`. Every item ships with
its Molecule scenarios / unit tests (see `CLAUDE.md`).

## 2. Bring in AFPI (Fedora, `personal` profile)

- [ ] Port the roles with the specific tasks in `tasks/Fedora.yml`; fill `catalog.yml` and
      `packages.yml` from AFPI's lists. Done: repos (RPM Fusion, Brave, VS Code, GitHub CLI, ASUS
      COPR), the application lists (DNF common/KDE/GNOME, Flatpaks, ClamAV and Steam as
      features), fonts, codecs (ffmpeg swap, @multimedia on Fedora) and Intel/AMD video
      acceleration (hardware features). Left: NVIDIA driver + `akmods_mok` (Fedora; Vulkan,
      VA-API, `/etc/modprobe.d/nvidia.conf`), then VirtualBox as a feature.
- [ ] ASUS feature tasks beyond the packages (`/etc/asusd`, `supergfxd.service`, ROG GUI
      autostart); needs a systemd image in Molecule.
- [ ] Personal aliases (`open/close-thevoid`, LUKS UUID) to `host_vars`.
- [ ] Feature gates: VirtualBox (string match today), ClamAV (unconditional freshclam), Flatpak overrides only for installed apps.
- [ ] `flatpak_filesystem_overrides` empty in the repo, ZapZap in `custom.yml.example`.

## 3. Bring in AAPI (AlmaLinux 10, `work` profile)

- [ ] `group_vars/os_AlmaLinux_10` + `tasks/RedHat.yml` (dnf4, CRB/EPEL, Oracle VirtualBox).
- [ ] Cleanup of both legacy `.zshrc` blocks.

## 4. Parity

- [ ] Golden test: resolved sets per (distro, profile, DE) compared with AFPI and AAPI.
- [ ] `fedora:44` and `almalinux:10` containers, twice (idempotency).
- [ ] VM with EFI + Secure Boot (also: the transient hostname, which containers cannot change).
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

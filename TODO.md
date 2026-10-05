# TODO — ALPI

Only what is left. Architecture, rationale and decisions in `PROPOSAL.md`. Every item ships with
its Molecule scenarios / unit tests (see `CLAUDE.md`).

## 2. Bring in AFPI (Fedora, `personal` profile)

- [ ] Port the roles with the specific tasks in `tasks/Fedora.yml`; fill `catalog.yml` and
      `packages.yml` from AFPI's lists (the catalog has only a seed today).
- [ ] Apply `system_hostname` (only when the profile has `alpi_manage_hostname`) and the git identity.
- [ ] New `repos` role (RPM Fusion, COPR) running first. Then drop the repo-related
      `packages_skip` from the Molecule scenarios and cover real Flatpak installs.
- [ ] Personal aliases (`open/close-thevoid`, LUKS UUID) to `host_vars`.
- [ ] Feature gates: VirtualBox (string match today), ClamAV (unconditional freshclam), Flatpak overrides only for installed apps.
- [ ] `flatpak_filesystem_overrides` empty in the repo, ZapZap in `custom.yml.example`.

## 3. Bring in AAPI (AlmaLinux 10, `work` profile)

- [ ] `group_vars/os_AlmaLinux_10` + `tasks/RedHat.yml` (dnf4, CRB/EPEL, Oracle VirtualBox).
- [ ] Cleanup of both legacy `.zshrc` blocks.

## 4. Parity

- [ ] Golden test: resolved sets per (distro, profile, DE) compared with AFPI and AAPI.
- [ ] `fedora:44` and `almalinux:10` containers, twice (idempotency).
- [ ] VM with EFI + Secure Boot.
- [ ] Freeze AAPI and AFPI with a README pointing to ALPI.

## 5. New distros (after parity, only with a test VM)

- [ ] Debian 13.
- [ ] Ubuntu 26.04 LTS.

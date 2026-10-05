# TODO — ALPI

Only what is left. Architecture, rationale and decisions in `PROPOSAL.md`.

## 1. Skeleton

- [ ] `bootstrap.sh` with detection via `/etc/os-release` (dnf/apt) and collections pinned per version.
- [ ] `site.yml` + `tasks/env_setup.yml`: support matrix (assert) → detection → `group_by`.
- [ ] `group_vars/os_*` and `group_vars/profile_*` with `ansible_group_priority`.
- [ ] `catalog.yml` + package resolution (single `set_fact`) + id validation (fail early).
- [ ] `packages_absent`: explicit uninstall, no autoremove; error if an id is both installed and absent.
- [ ] Support matrix with reserved Debian 13 / Ubuntu 26.04 slots (asserted as unsupported for now).
- [ ] `host_vars/127.0.0.1/{bootstrap,custom}.yml` + `custom.yml.example`.

## 2. Bring in AFPI (Fedora, `personal` profile)

- [ ] Port the roles with the specific tasks in `tasks/Fedora.yml`.
- [ ] New `repos` role (RPM Fusion, COPR) running first.
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

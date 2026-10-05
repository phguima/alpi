# TODO — ALPI

Only what is left. Architecture, rationale and decisions in `PROPOSAL.md`. Every item ships with
its Molecule scenarios / unit tests (see `CLAUDE.md`).

## 1. Molecule tests (before section 2)

- [ ] Install Molecule with the podman driver (pipx, see `CLAUDE.md`) and add a `requirements`
      note for it to the README.
- [ ] Make the plays testable outside `localhost` (Molecule's inventory): the real run keeps
      `inventory.ini`, the scenarios point `converge.yml` at the container.
- [ ] pytest unit tests for `filter_plugins/alpi.py` (`alpi_resolve`, `alpi_canonical`,
      `alpi_features`): raw prefixes, aliases, key order, `~`, missing keys, hardware veto.
- [ ] Scenarios `fedora44-personal` and `el10-work`: resolution (`--tags resolve` output) and the
      `packages` role (base, extras, absent), with `verify.yml` checking installed/removed packages.
- [ ] Failure scenario(s): unknown id, conflict, unknown feature, missing profile, strict mode,
      bad `pkg:`/`flatpak:` names, unsupported distro (`debian:13`): assert the run fails with the
      expected message.
- [ ] `bootstrap.sh` test (scripted answers via `script`, sudo shim; see `CLAUDE.md`).

## 2. Bring in AFPI (Fedora, `personal` profile)

- [ ] Port the roles with the specific tasks in `tasks/Fedora.yml`; fill `catalog.yml` and
      `packages.yml` from AFPI's lists (the catalog has only a seed today).
- [ ] Apply `system_hostname` (only when the profile has `alpi_manage_hostname`) and the git identity.
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

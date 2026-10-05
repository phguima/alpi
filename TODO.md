# TODO — ALPI

Only what is left. Architecture, rationale and decisions in `PROPOSAL.md`. Every item ships with
its Molecule scenarios / unit tests (see `CLAUDE.md`).

## Resume here (2026-10-05)

Committed as **work in progress, not fully tested**. In that commit:
- Catalog and package lists ported from AFPI 2.9 / AAPI 1.1 (plus `curl`); ClamAV as a feature.
- New `catalog` Molecule scenario with reviewed golden sets (`molecule/catalog/host_vars/`).
- Install-scenario verifies rewritten (`shared/verify_installed.yml`, heaviest apps skipped).
- Desktop-detection fix: the controller's `XDG_CURRENT_DESKTOP` only on `local` connections
  (under Molecule it leaked the host's KDE session into the containers).
- `failures` scenario: repos before packages in the "names not found" case; strict-mode
  expectation lists every unavailable id on EL.
- `.gitignore`: `/host_vars/` (root only). Before this, every `molecule/<scenario>/host_vars/`
  was ignored, so the scenarios pushed in `c9fe6f2`, `fa455aa` and `c952aff` lacked their
  settings; they are tracked from this commit on.

Before testing: `molecule destroy --all` from `tools/alpi` (an `alpi-fedora44-personal`
container was left running when the suite was interrupted).

Test status:
- Passed after the fixes: `el10-work`; `catalog` (before the desktop fix, with KDE/GNOME forced).
- Not rerun after the fixes: `fedora44-personal`, `failures`, `unsupported`, `bootstrap`, pytest.
  The full `molecule test --all` was interrupted.

Next steps:
1. pytest + `molecule test --all` (~35–45 min); fix what fails.
2. If green, drop this block and commit `test(catalog): validate the AFPI/AAPI application lists`
   with the results.

## 2. Bring in AFPI (Fedora, `personal` profile)

- [ ] Port the roles with the specific tasks in `tasks/Fedora.yml`; fill `catalog.yml` and
      `packages.yml` from AFPI's lists. Done: repos (RPM Fusion, Brave, VS Code, GitHub CLI, ASUS
      COPR) and the application lists (DNF common/KDE/GNOME, Flatpaks, ClamAV and Steam as
      features). Left for their roles: hardware (Intel/AMD/NVIDIA, codecs), fonts, VirtualBox.
- [ ] ASUS feature tasks beyond the packages (`/etc/asusd`, `supergfxd.service`, ROG GUI
      autostart); needs a systemd image in Molecule.
- [ ] Apply `system_hostname` (only when the profile has `alpi_manage_hostname`) and the git identity.
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

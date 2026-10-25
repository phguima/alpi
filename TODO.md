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
- A third controller line: Debian's ansible-core 2.19 (Data Tagging) next to EL10's 2.16 and
  Molecule's 2.21; `debian13-personal` resolves with the container's own ansible-core, as
  `el10-work` does (`shared/verify_native_controller.yml`).

### Phase 2 — shared apt layer (`family_Debian`)

- [ ] **Tests:** `shared/prepare.yml` already installs python3/sudo with apt; add removing
       `/etc/apt/apt.conf.d/docker-clean` (or the apt cache volume keeps nothing) and
       `/usr/sbin/policy-rc.d` (exit 101: services never start). `shared/verify_installed.yml` gets
       a dpkg path (`rpm -q --whatprovides` and dnf groups today). systemd scenarios need a
       Dockerfile, like `asus` (no `-init` images).

### Phase 3 — Debian 13

- [ ] **Support:** `Debian: {min: 13, max: 13}`; `unsupported` moves to `debian:12`.
- [ ] **`group_vars/os_Debian/`:** `zsh_aliases_os`, components (catalog keys, `mok_password` and the
      `virtualbox` repository are there since the `debian13` scenario).
- [ ] **`bootstrap.sh`:** a `debian)` branch. With a root password set at install, Debian installs no
      `sudo` at all: detect it and print `su - -c "apt install sudo && usermod -aG sudo $USER"` (`su -`:
      plain `su` lacks `/usr/sbin`), then log in again.
- [ ] **`pick.py`:** `"debian": "Debian"` (its unit test's fake Debian changes from unsupported).
- [ ] **NVIDIA:** DKMS key created and enrolled before `nvidia-driver` installs, then `nvidia.conf`.
      Debian's `steam.desktop` (steam-installer, checked 2026-10-25) has no `PrefersNonDefaultGPU`,
      unlike Fedora's: on a hybrid laptop Steam starts on the integrated GPU. Decide (a user copy
      with the key added, or nothing) after checking on a VM.

### Phase 4 — Ubuntu 26.04 LTS

- [ ] **Support:** `Ubuntu: {version: "26.04"}` (`alpi_support` takes exact versions);
      `unsupported` adds a 26.10 case (faked `os-release` if no image).
- [ ] **`group_vars/os_Ubuntu/`:** catalog keys, `mok_password`, `zsh_aliases_os`, `universe` and
      `multiverse`, the `virtualbox` repository (`resolute`).
- [ ] **`bootstrap.sh`, `pick.py`:** `ubuntu` branches (the picker's tests already fake Ubuntu).
- [ ] **Catalog `ubuntu` values** where they differ from `deb`: `chromium` → Flatpak, restricted
      codecs (decision 6: `ubuntu-restricted-addons` + `libavcodec-extra`), NVIDIA (decision 4:
      `nvidia-driver-NNN-open`, NNN pinned in `group_vars/os_Ubuntu`).
- [ ] **DKMS key = VirtualBox's key file.** Ubuntu's DKMS signs with
      `/var/lib/shim-signed/mok/MOK.{priv,der}`, the path `roles/virtualbox` already uses; when it is
      missing at build time DKMS runs `update-secureboot-policy`, a debconf prompt. Create and enroll
      it before any DKMS package (one key, one enrollment, shared by both).
- [ ] **AppArmor:** Ubuntu restricts unprivileged user namespaces, so Electron AppImages (Antigravity
      IDE) fail their sandbox; `roles/ai_tools` adds an AppArmor profile with `userns,` *(check)*.

### Phase 5 — tests and release

- [ ] **Scope:** an apt instance only where an apt code path exists (`catalog`, `failures`,
      `unsupported`, `update`, `boot`, `memory`, `secureboot`, `user`, `bootstrap`, `services`), not
      every scenario. `full` takes ~15 min (4 at a time) and grows with each instance; give
      `tests/run.sh` an `apt` list to run those alone while working.
- [ ] **New:** `ubuntu2604-personal` (real installs); `debian13-personal` exists and runs every role
      once it is ported (its skip-tags shrink).
- [ ] **`failures` on apt:** an unknown name and an unreadable source (`check_Debian.yml`; only
      the parser has unit tests).
- [ ] **VM checklist:** Debian 13 GNOME and KDE, Ubuntu 26.04 and Kubuntu 26.04, EFI + Secure Boot:
      MOK enrollment, `update-grub` and the GRUB menu, the reboot gate, VirtualBox next to KVM on
      Debian's 6.12, cedilla on KDE, the first run with unattended-upgrades still busy, the
      Antigravity IDE under AppArmor (Ubuntu), the installer's own `sources.list` (one-line, maybe
      a `cdrom:` line) getting `contrib`/`non-free` (only the images' deb822 file is tested).
- [ ] **Release:** after `tests/run.sh full` and the VM checklist per distro: Debian 13 as `v1.2.0`,
      Ubuntu 26.04 as `v1.3.0` (or one release if both land together).

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

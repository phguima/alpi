# Plan — Debian 13 and Ubuntu 26.04 LTS

Status: draft (2026-10-23), reviewed once by an adversarial agent; nothing implemented. Covers
`TODO.md` section 5. Once the decisions below are made they move to `PROPOSAL.md` ("Decisions
(…)") and the steps to `TODO.md`; this file is then removed. PROPOSAL decision 6 still holds: a
distro is supported only after it passes on a test VM.

Facts marked *(check)* are not confirmed yet and must be checked in a container or VM before code
relies on them. Everything else was confirmed against a source or the code (2026-10-23).

## Targets

| | Debian 13 "trixie" | Ubuntu 26.04 LTS "Resolute Raccoon" |
|---|---|---|
| Released | 2025-08 | 2026-04 |
| Kernel | 6.12 LTS | 7.0 |
| GNOME / KDE | GNOME 48 (gnome-terminal) / Plasma 6.3 | Ubuntu (GNOME, Ptyxis) / Kubuntu, Plasma 6.6 |
| ansible-core | 2.19.11 (Data Tagging) | 2.20.1 |
| Ansible facts | `Debian`, major `13`, `os_family: Debian` | `Ubuntu`, version `26.04`, major `26`, `os_family: Debian` |
| Docker image | `debian:13` | `ubuntu:26.04` |

Consequences:
- **Cedilla XWayland workaround** (`tasks/cedilla.yml`) turns on for both KDEs (KWin < 6.7).
- **VirtualBox vs KVM:** Debian's 6.12 kernel is below 6.16, where VirtualBox 7.2 starts sharing
  VT-x with KVM, so `/etc/modprobe.d/alpi-kvm.conf` is required there; on Ubuntu's 7.0 it is
  insurance, as on Fedora.
- **Ubuntu's major version is ambiguous:** `26` for both 26.04 and 26.10, so its support entry
  compares the full `distribution_version`.
- **Two controller versions to test against:** 2.19 (Debian) is a different line from 2.16 (EL10
  floor) and 2.21 (Molecule's venv); `debian13-personal` resolves with the container's own
  ansible-core, as `el10-work` does (`shared/verify_native_controller.yml`).

## Order

**Shared prerequisites and the apt layer first, then Debian 13, then Ubuntu 26.04 as a delta.**
Debian is the plainer base (no snaps, codecs in main); Ubuntu adds snaps, AppArmor limits, a
debconf EULA and `ubuntu-drivers`. VirtualBox comes from Oracle on both, so neither is harder
there. The alternative is Ubuntu first if a 26.04 machine is more pressing; Phase 1 is the same.

## Phase 0 — decisions

1. **Groups per family.** `env_setup.yml` only creates `os_<distro>` and `os_<distro>_<major>`, and
   a family group named `os_Debian` would collide with Debian's own. Add `family_<os_family>`
   (`family_RedHat`, `family_Debian`) to the `group_by` loop and to `pick.py`'s `load_data`, for
   data both apt distros share.
2. **Catalog keys `rpm` and `deb`.** 57 entries use `all:`, many with RPM-only names (`ImageMagick`,
   `lm_sensors`, `ShellCheck`, `fira-code-fonts`, `gstreamer1-*`…) that would resolve to wrong
   names on apt. `all` keeps only names that match everywhere. Key order:
   - Fedora: `fedora, rpm, all` · AlmaLinux 10: `el10, el, rpm, all`
   - Debian 13: `debian13, debian, deb, all` · Ubuntu 26.04: `ubuntu2604, ubuntu, deb, all`
3. **VirtualBox:** Oracle's apt repository on both (`download.virtualbox.org/virtualbox/debian`,
   suites `trixie` and `resolute`, package `virtualbox-7.2`; resolute had 7.2.22 on 2026-10-23,
   multiverse 7.2.6). Signed by `vboxdrv.sh` with the key in `/var/lib/shim-signed/mok`, the same
   code as EL. Extends PROPOSAL decision 5. Debian trixie has no `virtualbox` of its own (sid
   only).
4. **NVIDIA:**
   - Debian: `nvidia-driver` (non-free), built by DKMS, signed with DKMS's key
     (`/var/lib/dkms/mok.key`, `mok.pub`), enrolled through `roles/akmods_mok/tasks/enroll.yml`.
   - Ubuntu: a named `nvidia-driver-NNN` with Canonical's signed `linux-modules-nvidia-*`, not
     `ubuntu-drivers install`, which bypasses the catalog (name check, `verify_installed`,
     `packages_absent`). Which NNN, and how ALPI picks it *(check)*.
   - Both: i386 multiarch when `nvidia-driver` is selected too (Steam needs the `:i386` libraries).
5. **Snaps (Ubuntu):** leave snapd and its snaps (Firefox) alone; never map an id to a snap
   transitional package (`chromium` is `1snap1` there); use Flatpak.
6. **Restricted codecs (Ubuntu):** apt's noninteractive frontend declines the `ttf-mscorefonts`
   EULA, which fails `ubuntu-restricted-extras`. Preseed the debconf answer, or list the codec
   packages without the fonts.
7. **Unpackaged tools:** `uv` is in neither archive: `{pipx: uv}` or `{upstream: …}` on `deb`.
8. **MOK passwords:** `debian-alpi`, `ubuntu-alpi`.

## Phase 1 — prerequisites (no apt distro enabled; Fedora/EL golden values must not move)

1. **Gate roles on catalog ids, not native names** (CLAUDE.md already requires it):
   - `roles/virtualbox/vars/main.yml`: `^VirtualBox(-|$)` misses `virtualbox-7.2`, so the role
     (key, groups, `alpi-kvm.conf`) would be skipped silently. Use `'virtualbox' in
     alpi_ids_selected`; keep the akmod test for the build method only.
   - `roles/nvidia/vars/main.yml` (`'akmod-nvidia' in …`) → `'nvidia-driver' in
     alpi_ids_selected`.
   - `roles/akmods_mok` (`^akmod-`): becomes "which module signer this distro uses" (akmods, DKMS,
     none on Ubuntu's signed NVIDIA).
2. **`swap` per distro:** `swap: true` sits on the entry (`ffmpeg: {all: ffmpeg, swap: true}`), so
   `alpi_resolve` puts `ffmpeg` in `alpi_pkgs.swap` on apt too and `roles/packages` then calls
   `ansible.builtin.dnf`. Allow `swap` inside a per-distro value and gate the task on
   `family_RedHat`; unit tests.
3. **Family groups** (Phase 0.1) and `pick.py`.
4. **Catalog `rpm` key**, a pure rename on Fedora/EL, checked by the golden values. PROPOSAL's
   custom.yml example (`"rpm:sqlitebrowser"`, line 161) uses `rpm:` as a raw-name prefix: rename
   it there (`native:`) so it is not confused with the key.
5. **Support matrix:** an entry may give `version:` (exact) instead of `min`/`max`; the assert and
   its `fail_msg` (which renders `v.min`/`v.max`) handle both; `unsupported` and `failures`
   expectations follow.
6. **Version comparison:** dpkg versions carry an epoch (`kwin 4:6.6.6-0ubuntu0.1`), and
   `_version()` would read `(4, 6, 6, …)`, always below 6.7, so the workaround would never turn
   off. Read `${source:Upstream-Version}` with `dpkg-query`; unit test with epoch strings.

## Phase 2 — shared apt layer (`family_Debian`)

1. **`roles/repos`:**
   - `python3-debian` first (needed by `ansible.builtin.deb822_repository`).
   - A `deb822` type; `alpi_repos_common` entries keyed per family (`{yum: …, deb822: …}`, one
     `type` per id today).
   - Vendor files and keys under the **vendor's own names**: VS Code's `.deb` writes
     `vscode.sources` with `/usr/share/keyrings/microsoft.gpg`, and a second file with another
     `Signed-By` makes `apt update` fail *(check)*. Or preseed `code/add-microsoft-repo false`.
   - Components (`contrib`/`non-free`, `universe`/`multiverse`) in both formats: Debian's
     installer writes a one-line `/etc/apt/sources.list` (maybe with a `cdrom:` line) *(check)*,
     the images and Ubuntu use deb822 `.sources`.
2. **apt in general:** `DEBIAN_FRONTEND=noninteractive`; `lock_timeout` raised (unattended-upgrades
   and PackageKit hold the dpkg lock on a fresh install); `NEEDRESTART_MODE=a` on Ubuntu.
3. **`roles/packages`:** `check_Debian.yml` (`apt-get install -s` after `apt update`); `flatpak` and
   the Flathub remote (not installed on either); i386 multiarch when `steam` or `nvidia-driver` is
   selected (`steam-installer`: contrib on Debian, universe on Ubuntu).
4. **`roles/update`:** `apt full-upgrade`. Reboot gate: newest installed `linux-image-*` vs the
   running kernel, plus `/run/reboot-required` where present (Ubuntu). No `dnf_config`.
5. **`roles/boot`:** RedHat-only kernel tasks (`dnf repoquery`, debug kernels) gated off; handler
   `update-grub` instead of `grub2-mkconfig` (`roles/boot/handlers/main.yml`). Ubuntu's
   `/etc/default/grub.d/*.cfg` override `/etc/default/grub` and `GRUB_TIMEOUT_STYLE=hidden`
   hides the menu: write ALPI's settings as a `grub.d` drop-in there *(check)*.
6. **`roles/memory`:** `systemd-zram-generator` (it ships `/usr/lib/systemd/zram-generator.conf`
   with `[zram0]`, Fedora's `-defaults` role); `rpm -q` → per-family lookup.
7. **`roles/desktop`:**
   - Cedilla: locale from `/etc/default/locale` (Debian/Ubuntu), not `/etc/locale.conf`, or pt_BR
     users silently get the en_US Compose file.
   - Ptyxis tasks only when Ptyxis is installed (Debian GNOME uses gnome-terminal; `gsettings get
     org.gnome.Ptyxis` fails without the schema), or a `ptyxis` catalog id.
   - `.desktop` paths for Steam, Brave and VS Code *(check)*.
8. **`roles/zsh`:** `zsh_aliases_os` per distro (`full-update` with apt and the reboot hint).
9. **`roles/ai_tools`:** `libfuse2t64` instead of `fuse-libs`.
10. **Tests:** `shared/prepare.yml` already installs python3/sudo with apt; add removing
    `/etc/apt/apt.conf.d/docker-clean` (or the apt cache volume keeps nothing) and
    `/usr/sbin/policy-rc.d` (exit 101: services never start). `shared/verify_installed.yml` gets
    a dpkg path (`rpm -q --whatprovides` and dnf groups today). systemd scenarios need a
    Dockerfile, like `asus` (no `-init` images).

## Phase 3 — Debian 13

1. **Support:** `Debian: {min: 13, max: 13}`; `unsupported` moves to `debian:12`.
2. **`group_vars/os_Debian/`:** catalog keys, `mok_password`, `zsh_aliases_os`, components, the
   `virtualbox` repository (`trixie`).
3. **`bootstrap.sh`:** a `debian)` branch. With a root password set at install, Debian installs no
   `sudo` at all: detect it and print `su - -c "apt install sudo && usermod -aG sudo $USER"` (`su -`:
   plain `su` lacks `/usr/sbin`), then log in again.
4. **`pick.py`:** `"debian": "Debian"` (its unit test's fake Debian changes from unsupported).
5. **Catalog `debian`/`deb` values:** `chromium` is a real deb; `ffmpeg` and the GStreamer plugins
   are in main (`multimedia` → `~`); `discord`, `drawy`, `telegram` probably Flatpak;
   `asusctl`/`supergfxctl` and `mesa-va-drivers-freeworld` → `~`; `fastfetch`, `tuptime`, `hwinfo`,
   `nvtop` *(check, the `catalog` scenario decides)*.
6. **NVIDIA:** DKMS key created and enrolled before `nvidia-driver` installs, then `nvidia.conf`.

## Phase 4 — Ubuntu 26.04 LTS

1. **Support:** `Ubuntu: {version: "26.04"}` (Phase 1.5); `unsupported` adds a 26.10 case (faked
   `os-release` if no image).
2. **`group_vars/os_Ubuntu/`:** catalog keys, `mok_password`, `zsh_aliases_os`, `universe` and
   `multiverse`, the `virtualbox` repository (`resolute`).
3. **`bootstrap.sh`, `pick.py`:** `ubuntu` branches (the picker's tests already fake Ubuntu).
4. **Catalog `ubuntu` values** where they differ from `deb`: `chromium` → Flatpak, restricted
   codecs (Phase 0.6), NVIDIA (Phase 0.4).
5. **DKMS key = VirtualBox's key file.** Ubuntu's DKMS signs with
   `/var/lib/shim-signed/mok/MOK.{priv,der}`, the path `roles/virtualbox` already uses; when it is
   missing at build time DKMS runs `update-secureboot-policy`, a debconf prompt. Create and enroll
   it before any DKMS package (one key, one enrollment, shared by both).
6. **AppArmor:** Ubuntu restricts unprivileged user namespaces, so Electron AppImages (Antigravity
   IDE) fail their sandbox; `roles/ai_tools` adds an AppArmor profile with `userns,` *(check)*.

## Phase 5 — tests and release

- **Scope:** an apt instance only where an apt code path exists (`catalog`, `failures`,
  `unsupported`, `update`, `boot`, `memory`, `secureboot`, `user`, `bootstrap`, `services`), not
  every scenario. `full` already takes ~64 min; give `tests/run.sh` an `apt` list to run those
  alone while working.
- **New:** `debian13-personal`, `ubuntu2604-personal` (real installs).
- **VM checklist:** Debian 13 GNOME and KDE, Ubuntu 26.04 and Kubuntu 26.04, EFI + Secure Boot:
  MOK enrollment, `update-grub` and the GRUB menu, the reboot gate, VirtualBox next to KVM on
  Debian's 6.12, cedilla on KDE, the first run with unattended-upgrades still busy, the
  Antigravity IDE under AppArmor (Ubuntu).
- **Release:** after `tests/run.sh full` and the VM checklist per distro: Debian 13 as `v1.1.0`,
  Ubuntu 26.04 as `v1.2.0` (or one release if both land together).

## Sources

- Debian 13: [release overview](https://alternativeto.net/news/2025/8/debian-13-trixie-released-with-linux-kernel-6-12-lts-gnome-48-kde-6-3-and-more/)
- Ubuntu 26.04: [release announcement](https://discourse.ubuntu.com/t/ubuntu-26-04-resolute-raccoon-lts-released/80833),
  [kernel 7.0](https://discourse.ubuntu.com/t/26-04-lts-resolute-raccoon-shipping-with-the-final-7-0-linux-kernel/80838),
  [Kubuntu 26.04 with Plasma 6.6](https://lecrabeinfo.net/telecharger/kubuntu-26-04-lts/)
- Oracle apt repository: [suites](https://download.virtualbox.org/virtualbox/debian/dists/)
  (`trixie`, `resolute`)
- VirtualBox/KVM: [VirtualBox 7.2 changelog](https://www.virtualbox.org/wiki/Changelog-7.2)
  (KVM APIs on kernel 6.16+)

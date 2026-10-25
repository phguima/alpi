# TODO history — ALPI

Done items moved out of `TODO.md`, in its section order, each with the date it was finished and
its commit. Newer entries go at the end of their section; a new section is added when `TODO.md`
closes one. Rebuilt on 2026-10-24 from `TODO.md`'s git history (items edited over time keep their
final wording; the VM checklist steps live in `tests/vm-checklist.md`).

## 0. Open decisions

- **2026-10-05** All six recorded in `PROPOSAL.md` (`eb79382`): `packages_absent` (explicit
  uninstall), an unknown catalog id stops the run, what profiles carry (profiles later replaced
  by the picker), the VirtualBox source per distro, no Debian/Ubuntu port without a test VM,
  GNOME and KDE from the first batch.

## 1. Skeleton and Molecule tests

- **2026-10-05** Skeleton: `bootstrap.sh` (distro detection via `/etc/os-release`), `site.yml` +
  `tasks/env_setup.yml` (support matrix assert → detection → `group_by`), `group_vars/os_*`,
  `catalog.yml` with package resolution and id validation, `packages_absent`, support matrix with
  Debian 13 / Ubuntu 26.04 asserted as unsupported, `host_vars/127.0.0.1/{bootstrap,custom}.yml`
  + `custom.yml.example` (`c9fe6f2`).
- **2026-10-05** Every package name checked before installing (`pkg:`, `flatpak:`) (`b7a583a`).
- **2026-10-05** Molecule with the podman driver, plays testable outside `localhost`, pytest unit
  tests for `filter_plugins/alpi.py`, the `fedora44-personal`, `el10-work`, `failures`,
  `unsupported` and `bootstrap` scenarios (`815fcfc`, `fa455aa`).

## 2. Bring in AFPI (Fedora, personal machine)

- **2026-10-05** Repositories: RPM Fusion, Brave, VS Code, GitHub CLI, ASUS COPR (`c952aff`).
- **2026-10-06** Application lists: DNF common/KDE/GNOME, Flatpaks, ClamAV and Steam as features
  (`0649a6a`, validated in `9080809`).
- **2026-10-06** `system_hostname` and the git identity (`8d90381`).
- **2026-10-06** Fonts, codecs (ffmpeg swap, @multimedia on Fedora), Intel/AMD video acceleration
  (`5b24977`).
- **2026-10-06** NVIDIA driver + `akmods_mok` (`56afb1b`).
- **2026-10-06** VirtualBox as a feature: RPM Fusion akmod on Fedora, Oracle repository + own key
  on EL; driven by the resolved set, no string match (`7faa73d`).
- **2026-10-06** ClamAV: `roles/clamav` enables freshclam only when its package was resolved
  (`ca8b28e`).
- **2026-10-08** Profiles replaced with the package picker (`pick.py`, `selection.yml`), listing
  only what the running distro offers (`667c8b2`).
- **2026-10-08** Flatpak overrides only for apps being installed; `flatpak_filesystem_overrides`
  empty in the repo, ZapZap in `custom.yml.example` (`f2ccd31`).
- **2026-10-08** ASUS tasks beyond the packages (`/etc/asusd`, `supergfxd.service`, ROG GUI
  autostart), with a Fedora 44 + systemd image built by the `asus` scenario (`4b695f9`).
- **2026-10-08** zsh/Oh My Zsh setup; personal aliases (`open/close-thevoid`, LUKS UUID) moved to
  `host_vars` (`luks_volumes`, `zsh_aliases_custom` in `custom.yml`) (`25717cc`).
- **2026-10-09** System update (`update` role): dnf configuration, full upgrade, stop when a reboot
  is needed (`763208f`).
- **2026-10-09** Kernel maintenance (old and debug kernels, debug repositories) and GRUB settings
  (`46871c7`).
- **2026-10-09** Desktop: `~/wks`, Konsole profile and colors (KDE), Ptyxis settings (GNOME),
  cedilla (`.XCompose`) (`00b48e3`).
- **2026-10-09** API keys block in `.zshrc` (user only, from the optional vault) (`14cc1ea`).
- **2026-10-09** pipx tools (markitdown, notebooklm-py with Playwright, pdf2docx) as catalog
  entries (`8528fad`).
- **2026-10-10** Claude Code, Antigravity CLI and IDE (AppImage, menu entry) as features
  (`ff05304`).
- **2026-10-10** GRUB: AFPI's `GRUB_GFXPAYLOAD=keep` is a no-op on BLS (the `blscfg` module sets
  `gfxpayload=keep` itself): dropped, and removed from `/etc/default/grub` (`9c382ac`).
- **2026-10-10** Steam launcher on the NVIDIA GPU (`6e4f49c`).

## 3. Bring in AAPI (AlmaLinux 10, work machine)

- **2026-10-09** Cleanup of both legacy `.zshrc` blocks (`14cc1ea`).
- **2026-10-10** Roboto from upstream on EL (AAPI's desktop role: latest GitHub release, replaced
  when the version changes) (`f468e8a`).
- **2026-10-10** `group_vars/os_AlmaLinux_10` (dnf4, CRB/EPEL, Oracle VirtualBox); AAPI's legacy
  repository ids kept, `gh auth login` reminder (`1dca75b`).

## 4. Parity

- **2026-10-13** Cedilla on KDE with KWin 6.6 (EL10, from AAPI): Chromium/Electron apps ignore
  `~/.XCompose` on native Wayland, so they run on XWayland; gated on the KWin version
  (`cedilla_xwayland: auto`, KWin < 6.7) and undone when it no longer applies (`c254add`); decided
  again after `roles/update`'s upgrade (`63bdab8`).
- **2026-10-21** `fedora:44` and `almalinux:10` containers, twice (idempotency): Molecule's
  idempotence step in every scenario; `tests/run.sh full` green.
- **2026-10-22** VM with EFI + Secure Boot, steps in `tests/vm-checklist.md`: Fedora 44 GNOME and
  KDE, AlmaLinux 10 GNOME and KDE, all ok (also the transient hostname, the NVIDIA akmod build,
  `dracut` and MOK enrollment, which containers only fake).
- **2026-10-22** Golden test: resolved sets per (distro, DE) compared with AFPI and AAPI (reviewed
  golden values in the `catalog` scenario).
- **2026-10-22** AAPI and AFPI frozen with a README pointing to ALPI (`9755bcd`).
- **2026-10-25** Steam on the NVIDIA GPU from its own launcher, checked on noir (Plasma 6.7.5,
  Wayland): with ALPI's user launcher moved aside, the menu entry's `PrefersNonDefaultGPU` gave
  every Steam process switcheroo-control's offload variables and `nvidia-smi` listed Steam. ALPI's
  launcher dropped; a user launcher with the offload (ALPI's or AFPI's) is removed
  (`refactor(desktop): Steam's own launcher on the NVIDIA GPU`).

## 5. New distros

- **2026-10-24** Phase 0 decisions for Debian 13 and Ubuntu 26.04, after checking the packages in
  `debian:13` and `ubuntu:26.04` containers: family groups, catalog keys `rpm`/`deb`, Oracle's
  VirtualBox repository on both, NVIDIA (DKMS on Debian, a pinned `-open` branch on Ubuntu), snaps
  left alone, Ubuntu codecs without the Microsoft fonts, `uv` through pipx, MOK passwords;
  recorded in `PROPOSAL.md`, the steps moved from `PLAN-DEBIAN-UBUNTU.md` into `TODO.md`
  (`docs: Debian and Ubuntu decisions recorded, steps in the TODO`).
- **2026-10-24** Phase 1: `roles/virtualbox`, `roles/nvidia` and `roles/akmods_mok` gate on catalog
  ids instead of RPM names (`^VirtualBox`, `akmod-nvidia`, `^akmod-`), which apt's `virtualbox-7.2`
  would have skipped silently; the akmods key also needs the distro's `kmod_signer: akmods`
  (`refactor(roles): gate the module roles on catalog ids`).
- **2026-10-24** Phase 1: `swap` per distro (`{native: …, swap: true|false}` overrides the entry's
  `swap`), and the `allowerasing` install runs only where dnf is the package manager
  (`feat(catalog): swap per distro, allowerasing on dnf only`).
- **2026-10-24** Phase 1: family groups, `family_<os_family>` in `env_setup`'s `group_by` and in
  `pick.py` (`FAMILIES`), loaded before `os_<distro>`; no family data yet (Fedora and EL share no
  key), `family_Debian` comes with the apt layer (`feat(env): family groups for shared distro data`).
- **2026-10-24** Phase 1: catalog key `rpm` (Fedora `fedora, rpm, all`, EL `el10, el, rpm, all`);
  the 14 `all:` names missing on Debian 13 or Ubuntu 26.04 (checked in containers) moved to it;
  PROPOSAL's `rpm:` raw-name example fixed to `pkg:` (`refactor(catalog): rpm key for the RPM names`).
- **2026-10-24** Phase 1: support matrix entries may give an exact `{version: "26.04"}` besides
  `{min, max}` majors; the check and its message moved into the `alpi_support` filter
  (`feat(env): exact versions in the support matrix`).
- **2026-10-24** Phase 1: KWin versions compared without a dpkg epoch or revision (`4:6.7.0-1` read
  as 4.x would have kept the cedilla workaround on forever), and KWin read with `dpkg-query`'s
  `source:Upstream-Version` of `kwin-wayland` on Debian/Ubuntu (`fix(desktop): KWin versions
  with a dpkg epoch`). Phase 1 done.
- **2026-10-24** Phase 2 foundation (pulled from Phase 3.2/3.5): `debian13` scenario (Debian 13
  allowed in its own host_vars, resolution against reviewed golden values), `group_vars/os_Debian`
  (catalog keys, `mok_password`, `kmod_signer: dkms`, the Oracle VirtualBox deb822 repository), a
  `debian` value for every catalog entry (names checked with `apt-cache`), apt test images without
  `docker-clean` and `policy-rc.d` (`test(debian13): resolution on Debian 13, catalog values`).
- **2026-10-24** Phase 2: `roles/repos` on apt. Repository definitions per family
  (`alpi_repos_family`, `group_vars/family_<os_family>/repos.yml`); Debian's `contrib`/`non-free`
  components in either source format; Brave, VS Code, GitHub CLI and VirtualBox as deb822 files
  under the vendor's own file and keyring names, since a second file with another `Signed-By`
  (VS Code's `.deb` writes `vscode.sources`) makes apt refuse every source; no preseed needed
  (`feat(repos): apt repositories for the Debian family`).
- **2026-10-25** Phase 2: apt in general and `roles/packages` on apt. `site.yml` gets the
  family's `apt_environment` (no debconf or needrestart prompts) and `apt_lock_timeout` (600 s,
  passed on by `ansible.builtin.package`); `check_Debian.yml` reads `apt-get update` (exit 0 on
  an unreachable source) and `apt-get install -s` (`alpi_apt_simulation`); i386 multiarch for
  Steam and NVIDIA in `roles/repos`; `debian13` checks every name with apt, `brave-origin` and the
  other vendor names included (Phase 3's "Catalog on apt" with it); new `debian13-personal`
  installs for real through `site.yml` (`feat(packages): apt name check, i386, apt settings`).
- **2026-10-25** Phase 2: `roles/update` on apt, the upgrade and reboot signals per family
  (`alpi_reboot_needed`): `apt-get dist-upgrade`, then `/run/reboot-required` or a newer
  `linux-image-<release>` than the running kernel stops the play; three Debian instances in
  `update` (`feat(update): full upgrade and reboot gate on apt`).
- **2026-10-25** Phase 2: `roles/boot` on apt. Kernel maintenance is dnf's only; GRUB settings
  as the drop-in `/etc/default/grub.d/99-alpi.cfg` with `GRUB_TIMEOUT_STYLE=menu`, handler
  `update-grub` (`grub_regenerate`, `grub_dropin` per family). On an Ubuntu VM: check that its
  installed `grub.d` files sort before `99-alpi` (Phase 5 checklist)
  (`feat(boot): GRUB drop-in and update-grub on apt`).
- **2026-10-25** Phase 2: `roles/memory` on apt: `systemd-zram-generator` (generator and its
  `[zram0]` file in one package; default size min(ram / 2, 4096)), found through `dpkg-query`
  (`zram_generator_query`, `zram_package` per family); two Debian instances in `memory`
  (`feat(memory): zram on apt`).
- **2026-10-25** Phase 2: the user roles on apt. `roles/desktop` reads the locale from
  `/etc/default/locale` too and sets Ptyxis only where its schema is installed; the menu entries
  of Steam, Brave and VS Code have the same names in Debian's packages (checked); `roles/zsh`'s
  `zsh_aliases_family` layer with apt's `full-update`; `roles/ai_tools` installs `libfuse2t64`;
  a Debian GNOME instance in `user` (`feat(user): zsh, desktop and AI tools on apt`).
- **2026-10-25** Phase 2: tests on apt. `shared/prepare.yml` already removed `docker-clean` and
  `policy-rc.d`, `verify_installed.yml` got its dpkg path with the packages item; new
  `shared/Dockerfile-systemd-apt.j2` (systemd for Debian and Ubuntu, which publish no init
  image), first used by a Debian instance in `services`
  (`test(services): systemd image for apt, freshclam on Debian`). Phase 2 done.
- **2026-10-25** Phase 3: Debian 13 in the support matrix (release after the VM checklist);
  `pick.py` maps `debian`; `bootstrap.sh` installs Debian's ansible-core (apt kept off the
  terminal, or debconf takes the piped answers) and stops with the `su -` command when there is
  no sudo; `unsupported` moved to Debian 12; the tests' Debian overrides removed
  (`feat(env): Debian 13 in the support matrix`).
- **2026-10-25** Phase 3: Secure Boot and NVIDIA on Debian. `kmod_signers` replaces `kmod_ids`:
  `roles/akmods_mok` creates DKMS's key (`dkms generate_mok`, `/var/lib/dkms/mok.pub`) for
  `nvidia-driver` and enrolls it; `roles/nvidia` writes its options for Debian's renamed module
  (`nvidia-current`) to `alpi-nvidia.conf`, leaving Debian's own `nvidia.conf` alone, and builds
  with `dkms autoinstall` when the module is missing; a Debian instance in `secureboot`
  (`feat(secureboot): DKMS key and NVIDIA settings on Debian`). The Steam GPU question and the
  real enrollment went to Phase 5's VM checklist. Phase 3 done.
- **2026-10-25** Phase 4: Ubuntu 26.04 in the catalog and the support matrix (release after the
  VM checklist). `deb` key for the 34 names Debian and Ubuntu share (checked in `ubuntu:26.04`);
  Ubuntu's own values: Chromium as a Flatpak, codecs (`ubuntu-restricted-addons`,
  `libavcodec-extra`), the pinned NVIDIA 615 open branch with Canonical's signed modules, generic
  headers; Steam's 32-bit NVIDIA libraries on both apt distros; `group_vars/os_Ubuntu`
  (components, Oracle's resolute suite, `ubuntu-alpi`); `pick.py` and `bootstrap.sh` branches;
  new `ubuntu2604` scenario on `debian13`'s playbooks; `unsupported` adds Ubuntu 26.10
  (`feat(ubuntu): catalog, repositories and support for Ubuntu 26.04`).
- **2026-10-25** Phase 4: one Secure Boot key on Ubuntu, the `shim` signer:
  `update-secureboot-policy --new-key` before DKMS or Oracle's `vboxdrv.sh` sign anything, so
  one enrollment covers both (`feat(secureboot): one shim-signed key on Ubuntu`).
- **2026-10-25** Phase 4: an AppArmor profile granting `userns` to the Antigravity IDE on Ubuntu,
  whose sandbox needs user namespaces (`feat(ai_tools): AppArmor profile for the Antigravity IDE
  on Ubuntu`). Phase 4 done; the VM checks are in Phase 5.
- **2026-10-25** Phase 5, the container part: apt instances in every scenario with an apt code
  path (`catalog`'s job done by `debian13`/`ubuntu2604`), `tests/run.sh apt`; `failures` on
  Debian 13 (unknown names, unmet dependencies from a local repository, an unreachable source:
  the apt message now starts as dnf's); new `ubuntu2604-personal`; `tests/vm-checklist-apt.md`
  for the four VMs (`test: apt failure cases, ubuntu2604-personal, the apt VM checklist`).
- **2026-10-25** Steam on the NVIDIA GPU on Debian and Ubuntu: steam-installer's launcher has no
  `PrefersNonDefaultGPU` (unlike Fedora's), so ALPI writes a user copy with it while the driver
  and Steam are selected (`alpi_steam_launcher`, `steam_gpu_launcher` in `family_Debian`)
  (`feat(desktop): Steam's launcher asks for the NVIDIA GPU on Debian and Ubuntu`). Real hardware
  still to check.
- **2026-10-25** `debian13-personal` and `ubuntu2604-personal` also resolve with the distro's own
  ansible-core (2.19, 2.20), as `el10-work` does with EL10's 2.16: the controller `bootstrap.sh`
  installs there (`test: resolution with Debian's and Ubuntu's own ansible-core`).
- **2026-10-25** `v1.2.0` tagged on `f0ca853` (full green): the picker's aliases and Steam's own
  launcher for Fedora and EL, Debian 13 and Ubuntu 26.04 in the matrix as a preview, not
  VM-checked; their real releases move to `v1.3.0`/`v1.4.0`
  (`docs(todo): v1.2.0 tagged, Debian and Ubuntu releases renumbered`).

## 6. Swap (zram)

- **2026-10-14** `roles/memory`: zram through zram-generator on Fedora and EL, decided from the
  machine's swap, zswap and zram-generator setup; hibernation reminder (`c73cc19`).
- **2026-10-22** Checked on the AlmaLinux 10 work machine and on noir: the `zram_apply` steps
  containers skip (`zramctl`, `swapon --show` priority 100, `vm.swappiness` 180,
  `vm.page-cluster` 0; a second run reports no changes) (`1de0a02`).

## Maintenance

- **2026-10-23** VirtualBox vs KVM on kernel 6.12+: kvm keeps VMX on from load
  (`enable_virt_at_load=Y`), so VirtualBox VMs failed with `VERR_VMX_IN_VMX_ROOT_MODE` on the
  AlmaLinux 10 work machine. `/etc/modprobe.d/alpi-kvm.conf` (`options kvm enable_virt_at_load=0`),
  removed when VirtualBox is off; applies after a reboot. noir was fine because VirtualBox 7.2.2+
  shares VT-x with KVM on kernels 6.16+ (`86f1978`).
- **2026-10-24** VLC and HEIF/HEVC freeworld codecs (`vlc-plugins-freeworld`,
  `libheif-freeworld`, carried over from AAPI): waited for stable EPEL, which on 2026-10-24 had
  `vlc-libs` 3.0.24 and `libheif` 1.23.6, what both require; added to the catalog (`all`) and
  `packages_base` (`326b3d6`). Never enable `epel-testing` for them.
- **2026-10-24** Freeworld builds lagging behind EPEL: `roles/update` upgrades with `nobest` (EL's
  `best=True` failed the run until RPM Fusion rebuilt), and the name check fails early, naming the
  package, when dependencies do not resolve (dry run with `--allowerasing`, like the swaps)
  (`bf9a163`).
- **2026-10-24** Recheck after Molecule 26.9.0 → 26.10.0: expected log noise unchanged; the only
  deprecation, `bool` on an int in `molecule/user/verify.yml`, had made three absence checks
  always pass, fixed (`d5de497`).

# TODO — ALPI

Work plan. Done items are ticked (with the commit); a section is removed once all its items are
ticked. Architecture, rationale and decisions in `PROPOSAL.md`. Every item ships with its Molecule
scenarios / unit tests (see `CLAUDE.md`).

## 4. Parity

- [x] Golden test: resolved sets per (distro, DE) compared with AFPI and AAPI (reviewed
      golden values in the `catalog` scenario; confirmed 2026-10-22).
- [x] `fedora:44` and `almalinux:10` containers, twice (idempotency): Molecule's idempotence
      step in every scenario; `tests/run.sh full` green on 2026-10-21.
- [x] VM with EFI + Secure Boot, steps in `tests/vm-checklist.md` (Fedora 44 GNOME and KDE,
      AlmaLinux 10 GNOME and KDE, all ok on 2026-10-21/22) (also: the transient hostname, which containers cannot change; the
      NVIDIA akmod build, `dracut` and MOK enrollment, which containers only fake; `e` on a GRUB
      entry shows `set gfxpayload=keep` without `GRUB_GFXPAYLOAD`).
- [ ] On noir: does Steam run on the NVIDIA GPU from its own launcher (`PrefersNonDefaultGPU`,
      `X-KDE-RunOnDiscreteGpu`, via switcheroo-control) without ALPI's user launcher
      (`feat(desktop): …`)? If so, drop the override.
- [x] Cedilla on KDE with KWin 6.6 (EL10, from AAPI `fix(desktop): …`): Chromium/Electron apps
      ignore `~/.XCompose` on native Wayland, so they run on XWayland. Gated on the KWin version
      (`cedilla_xwayland: auto`, KWin < 6.7; EL10 has 6.6.4, the version Fedora 44 shipped with)
      and undone when it no longer applies (`c254add`); decided again after `roles/update`'s
      upgrade (`feat(desktop): decide the cedilla workaround again after the upgrade`).
- [x] Freeze AAPI and AFPI with a README pointing to ALPI (2026-10-22).

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
- [x] VLC and HEIF/HEVC freeworld codecs on EL (`vlc-plugins-freeworld`, `libheif-freeworld`,
      carried over from AAPI's TODO): left out because RPM Fusion builds them against newer
      libraries than stable EPEL ships. On 2026-10-04 both only waited for stable EPEL (it had
      `vlc-libs` 3.0.23 and `libheif` 1.17.6; `epel-testing` had 3.0.24 and 1.23.5, which both
      require). Do not enable `epel-testing`; once stable has them, add both to the catalog (`el`)
      and `packages_base`. Re-check with CRB, EPEL and RPM Fusion enabled:
      `dnf repoquery --qf "%{name}-%{version}" vlc-libs libheif` vs
      `dnf repoquery --requires vlc-plugins-freeworld libheif-freeworld | grep -E "^(vlc-libs|libheif)"`.
      On 2026-10-24 stable EPEL had `vlc-libs` 3.0.24 and `libheif` 1.23.6, what both require:
      both added to the catalog (`all`) and `packages_base`
      (`feat(packages): VLC and HEIF freeworld codecs on every distro`).
- [x] VirtualBox vs KVM on kernel 6.12+: `kvm.enable_virt_at_load=Y` (the default) keeps VMX on
      while `kvm_intel` is loaded, even unused, so VirtualBox VMs fail with `VT-x is being used by
      another hypervisor (VERR_VMX_IN_VMX_ROOT_MODE)`. Seen on 2026-10-13 on the AlmaLinux 10 work
      machine (kernel 6.12.0-211.64.1.el10_2, VM `el10-kde-alpi`); worked around by hand with
      `sudo modprobe -r kvm_intel kvm` (until reboot). noir (kernel 7.2) runs VirtualBox VMs; why
      it differs is not checked yet. Candidate fix in `roles/virtualbox`:
      `/etc/modprobe.d/kvm.conf` with `options kvm enable_virt_at_load=0` (KVM still works, VMX is
      enabled only while a KVM guest runs), with a Molecule check of the file. Done as
      `/etc/modprobe.d/alpi-kvm.conf`, removed when VirtualBox is off
      (`fix(virtualbox): keep VMX off until a KVM guest runs`); on the real machine it applies
      after a reboot. noir differs because VirtualBox 7.2.2+ takes VT-x through KVM on kernels
      6.16+ (changelog); EL10 reports 6.12, so that code is compiled out there.

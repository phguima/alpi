# Hardware checklist: NVIDIA and Steam on noir, Debian 13 and Ubuntu 26.04 (TODO section 5, Phase 5)

What VMs cannot cover: the NVIDIA driver on a real hybrid GPU (Debian's 550 built and signed by
DKMS, Ubuntu's 615 with Canonical's signed modules) and Steam started from the menu landing on the
NVIDIA GPU through ALPI's launcher copy (`PrefersNonDefaultGPU`, switcheroo-control). Also MOK
enrollment on real firmware. Both distros are installed on an **external drive** and booted from
it; noir's Fedora on the internal disk must come out untouched, MOK list included.

| Install | Desktop | Covers |
|---|---|---|
| Debian 13 | **GNOME** | DKMS key + NVIDIA 550, `PrefersNonDefaultGPU` read by GNOME Shell |
| Kubuntu 26.04 | **KDE** | shim-signed key, Canonical's NVIDIA 615-open, `X-KDE-RunOnDiscreteGpu` read by Plasma |

Tick each step and note any failure under it. Send results as screenshots (`~/Pictures/Screenshots`)
or phone photos for firmware screens; each step says what to capture.

You need: a USB 3 SSD (or fast stick) of 128 GB or more for the two installs, a second stick for
the installers, noir on mains power.

## Step 0: baseline on noir's Fedora (before anything else)

Record the MOK list, the SBAT level, the boot entries and the internal ESP, so the cleanup can
tell what the tests added.

```bash
mkdir -p ~/mok-test/baseline && cd ~/mok-test/baseline
mokutil --sb-state                                   | tee ../sb-state.txt
sudo mokutil --list-enrolled                         > ../enrolled-before.txt
sudo mokutil --export && sudo chown "$USER": MOK-*.der
for f in MOK-*.der; do openssl x509 -inform der -in "$f" -noout -fingerprint -sha1; done \
  | sort > ../fingerprints-before.txt
openssl x509 -inform der -in /etc/pki/akmods/certs/public_key.der -noout -fingerprint -sha1 \
  | tee ../fedora-akmods-fingerprint.txt
sudo mokutil --list-sbat-revocations                 > ../sbat-before.txt
sudo efibootmgr -v                                   > ../efiboot-before.txt
sudo find /boot/efi/EFI -maxdepth 1                  > ../esp-before.txt
```

- [ ] `SecureBoot enabled`. 📸
- [ ] `fingerprints-before.txt` lists every enrolled key; Fedora's akmods fingerprint is among
      them (`grep -F -f ../fedora-akmods-fingerprint.txt ../fingerprints-before.txt`). 📸 both files.
- [ ] `esp-before.txt` has no `debian` or `ubuntu` directory. Keep `~/mok-test/` until step 6.

## Step 1: install both on the external drive

Write each ISO to the installer stick (`lsblk` first: the wrong `of=` wipes that disk):

```bash
sudo dd if=debian-13-amd64-netinst.iso of=/dev/sdX bs=4M status=progress oflag=sync
```

The installers like to put their bootloader on the **internal** disk's ESP. If noir's firmware
can disable the internal NVMe, do that for the installs and skip the partitioning care below.

- [ ] Debian 13: boot the stick (F8 / Esc for the boot menu), **Expert install**, no root
      password, "GNOME". Partitioning **manual**, only the external drive: a 512 MB ESP, then `/`
      on about half the drive. GRUB goes to the external drive's ESP ("Force GRUB installation to
      the EFI removable media path": **yes**, so it boots without an NVRAM entry).
- [ ] Kubuntu 26.04: **Manual installation**, the external drive as the boot device, its own
      512 MB ESP and `/` in the rest. Leave the internal disk's partitions unselected.
- [ ] Back in Fedora: `sudo find /boot/efi/EFI -maxdepth 1 | diff ~/mok-test/esp-before.txt -`
      → no output (nothing written to the internal ESP). Fedora still boots by default. 📸

## Step 2: first runs (each distro)

Boot the external drive from the firmware's boot menu. In the picker keep the defaults and make
sure **Steam** is checked and **NVIDIA** is not vetoed (it is detected: no `-e is_nvidia` here).

```bash
sudo apt-get install -y git
git clone https://github.com/phguima/alpi && cd alpi && ./bootstrap.sh   # hostnames: debian-noir, kubuntu-noir
ansible-playbook site.yml -K 2>&1 | tee run0.log
```

- [ ] `--tags resolve` (or the run's start) lists `nvidia-driver` and `steam-installer`. 📸
- [ ] The run stops at the reboot gate if the upgrade brought a kernel: reboot, then
      `ansible-playbook site.yml -K 2>&1 | tee run1.log`.
- [ ] Ends with `failed=0` and the MOK reminder: Debian `DKMS` (and `VirtualBox` if selected),
      Kubuntu `DKMS and VirtualBox` (one key, requested even for NVIDIA alone). 📸
- [ ] `sudo mokutil --list-new` → the pending key(s), with their subjects. 📸
- [ ] **Kubuntu only, before enrolling:** `nvidia-smi` already works (Canonical's modules are signed
      by a key shim trusts). 📸

## Step 3: MOK enrollment

- [ ] Reboot → blue MokManager → **Enroll MOK** → View key (subject matches step 2) → Continue →
      password `debian-alpi` / `ubuntu-alpi` → Reboot. 📸 (phone)
- [ ] `sudo mokutil --test-key /var/lib/dkms/mok.pub` (Debian) /
      `sudo mokutil --test-key /var/lib/shim-signed/mok/MOK.der` (both, where it exists) →
      "is already enrolled".
- [ ] `ansible-playbook site.yml -K 2>&1 | tee run2.log` → `changed=0`.

## Step 4: NVIDIA

```bash
nvidia-smi
cat /proc/driver/nvidia/version
lsmod | grep -E '^nvidia'
modinfo -F signer nvidia-current 2>/dev/null || modinfo -F signer nvidia
cat /etc/modprobe.d/alpi-nvidia.conf
switcherooctl list
```

- [ ] Debian: driver 550, signer `DKMS module signing key`; `options nvidia-current …`. If
      `nvidia-smi` is missing, `sudo apt install nvidia-smi` and note it (the catalog may need it). 📸
- [ ] Kubuntu: driver 615, signer Canonical's; `options nvidia …`;
      `dpkg -l | grep linux-modules-nvidia-615-open` installed, no `nvidia-dkms` build. 📸
- [ ] `switcherooctl list` shows two GPUs, the NVIDIA one not `Default: yes`. 📸
- [ ] `cat /sys/module/nvidia*/parameters/DynamicPowerManagement` (whichever module loaded) → 2.

## Step 5: Steam on the NVIDIA GPU

- [ ] `head -3 ~/.local/share/applications/steam.desktop` → ALPI's marker; `grep -E
      'PrefersNonDefaultGPU|X-KDE-RunOnDiscreteGpu|^Exec' ~/.local/share/applications/steam.desktop`
      → both keys `true`, no `env` on the Exec lines. 📸
- [ ] Start Steam **from the app menu** (not a terminal), let it update and log in. GNOME: the
      menu entry's right-click offers no "Launch using Discrete Graphics Card" (it is already
      the default). 📸
- [ ] `nvidia-smi` lists `steam` / `steamwebhelper` among the processes. 📸 **This is the TODO item.**
- [ ] Control: `steam` started from a terminal does **not** appear in `nvidia-smi` (proves the
      launcher, not something else, picks the GPU). Quit Steam first.
- [ ] Optional: a game's in-game overlay or `glxinfo -B` run through the launcher's GPU names
      the NVIDIA GPU.

If Steam stays on the integrated GPU: 📸 `switcherooctl list`, `journalctl --user -b | grep -i
switcheroo`, and note the desktop. The TODO says to drop the copy if switcheroo's offload does not
work there.

## Step 6: cleanup on noir's Fedora

Boot Fedora. Find the keys the tests enrolled by comparing with the baseline, and request their
deletion (MokManager confirms it on the next boot):

```bash
mkdir -p ~/mok-test/after && cd ~/mok-test/after
sudo mokutil --export && sudo chown "$USER": MOK-*.der
new=()
for f in MOK-*.der; do
  fp=$(openssl x509 -inform der -in "$f" -noout -fingerprint -sha1)
  if ! grep -qxF "$fp" ../fingerprints-before.txt; then
    new+=("$f"); echo "NEW: $f"; openssl x509 -inform der -in "$f" -noout -subject
  fi
done
```

- [ ] Only the test keys are `NEW` (subjects: Debian's DKMS key, Ubuntu's shim-signed MOK, any
      VirtualBox key); Fedora's akmods key is **not** among them
      (`grep -F -f ../fedora-akmods-fingerprint.txt` against each `NEW` file's fingerprint finds
      nothing). 📸 **Stop here if anything else shows up.**
- [ ] `sudo mokutil --delete "${new[@]}"` → set a one-time password (e.g. `delete-alpi`).
      `sudo mokutil --list-delete` → the same keys. 📸
- [ ] Reboot → MokManager → **Delete MOK** → View key → Continue → Yes → password → Reboot. 📸 (phone)
- [ ] Back in Fedora:

      ```bash
      cd ~/mok-test
      sudo mokutil --list-enrolled > enrolled-after.txt
      diff enrolled-before.txt enrolled-after.txt && echo "MOK list as before"
      sudo mokutil --test-key /etc/pki/akmods/certs/public_key.der   # is already enrolled
      sudo mokutil --list-sbat-revocations | diff sbat-before.txt -
      ```

      → "MOK list as before", Fedora's key enrolled; `lsmod | grep nvidia` (Fedora's akmod still
      loads). An SBAT diff is not a failure if Fedora boots (a newer shim raised the level), but
      note it. 📸
- [ ] NVRAM entries the installers added (`debian`, `ubuntu`): `sudo efibootmgr -v | diff
      ~/mok-test/efiboot-before.txt -`, then `sudo efibootmgr -b XXXX -B` for each new one. Fedora
      stays first in `BootOrder`. 📸
- [ ] Unplug the external drive; Fedora boots normally. Wipe the drive whenever you like.

## Results

(Notes per step, dated.)

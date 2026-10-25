# VM checklist: Debian 13 and Ubuntu 26.04 (TODO section 5, Phase 5)

What containers cannot cover on apt: real Secure Boot and MOK enrollment (DKMS's key on Debian,
shim-signed's on Ubuntu), modules built or shipped signed and loading, `update-grub` and the GRUB
menu, the reboot gate on a real kernel, unattended-upgrades holding the dpkg lock on a fresh
install, the installer's own apt sources, desktop sessions (cedilla, Ptyxis), and the Antigravity
IDE under Ubuntu's AppArmor. Four VMs in VirtualBox, all EFI + Secure Boot:

| VM | Install | Covers |
|---|---|---|
| `debian13-alpi`, Debian 13 **GNOME** | netinst, **root password set** | `bootstrap.sh` without sudo, the installer's one-line `sources.list`, gnome-terminal (no Ptyxis), DKMS key + NVIDIA module (forced on), Oracle VirtualBox |
| `debian13-kde-alpi`, Debian 13 **KDE** | netinst, no root password | cedilla on XWayland (KWin 6.3), Konsole |
| `ubuntu2604-alpi`, Ubuntu 26.04 **Desktop** | default | shim-signed key, Canonical's NVIDIA modules (forced on), Ptyxis, the Antigravity IDE under AppArmor, codecs |
| `kubuntu2604-alpi`, Kubuntu 26.04 | default | cedilla on XWayland (KWin 6.6), Konsole |

Tick each step and note any failure under it. Send results as screenshots
(`~/Pictures/Screenshots`); each step says what to capture. File transfer:
[vm-file-transfer.md](vm-file-transfer.md).

## Step 0: create the VMs (on the host, VirtualBox 7.2)

`mkvm` from [vm-checklist.md](vm-checklist.md), step 0:

```bash
mkvm debian13-alpi Debian_64 "$HOME/Downloads/debian-13-amd64-netinst.iso"   # adjust ISO names
mkvm debian13-kde-alpi Debian_64 "$HOME/Downloads/debian-13-amd64-netinst.iso"
mkvm ubuntu2604-alpi Ubuntu_64 "$HOME/Downloads/ubuntu-26.04-desktop-amd64.iso"
mkvm kubuntu2604-alpi Ubuntu_64 "$HOME/Downloads/kubuntu-26.04-desktop-amd64.iso"
```

- [ ] Install. Debian GNOME: **set a root password** (so the installer gives the user no sudo)
      and pick "GNOME". Debian KDE: **leave the root password empty** (the user gets sudo), pick
      "KDE Plasma". Ubuntu and Kubuntu: the defaults.
- [ ] In each VM: `mokutil --sb-state` → `SecureBoot enabled`; note `hostname`, `uname -r`, and
      on Debian `cat /etc/apt/sources.list; ls /etc/apt/sources.list.d/`. 📸 each.
- [ ] VM off, clean snapshot: `VBoxManage snapshot <vm> take clean`.

## Step 1: bootstrap (every VM)

Right after the first login, while unattended-upgrades may still be running:

```bash
sudo apt-get install -y git   # Debian GNOME: there is no sudo yet, see the next item
git clone https://github.com/phguima/alpi && cd alpi && ./bootstrap.sh
```

- [ ] Debian GNOME (no sudo): install git as root (`su - -c "apt install -y git"`), clone, run
      `./bootstrap.sh`: it stops at once and prints `su - -c "apt install sudo && usermod -aG sudo
      <you>"`. Run that, log out and in, run `./bootstrap.sh` again. 📸 the message.
- [ ] Installs `ansible-core`, `pciutils`, PyYAML, whiptail and `community.general` without
      errors or debconf questions; asks the hostname (`debian-alpi`, `debian-kde-alpi`,
      `ubuntu-alpi`, `kubuntu-alpi`) and the git identity; opens the picker (defaults: OK). 📸 the
      end of the output.
- [ ] Debian GNOME and Ubuntu: add `-e is_nvidia=true` to every `ansible-playbook` command below,
      so the NVIDIA path runs without an NVIDIA GPU (Debian: DKMS build and signing; Ubuntu:
      Canonical's modules). Snapshot first to roll the driver back later.
- [ ] `ansible-playbook site.yml -K --tags resolve` prints the sets; nothing changes. 📸 the
      native/flatpak lists (Ubuntu: Chromium among the Flatpaks, `ubuntu-restricted-addons` and
      `libavcodec-extra` among the native names).

## Step 2: first run, the lock and the reboot gate

```bash
ansible-playbook site.yml -K 2>&1 | tee run0.log
```

- [ ] If unattended-upgrades was still running, the run waits for the dpkg lock instead of
      failing ("Could not get lock"). Note whether it waited.
- [ ] Debian (installer's one-line `sources.list`): `grep -v '^#' /etc/apt/sources.list` → the
      release's lines have `main contrib non-free non-free-firmware`; a `cdrom:` line is left
      alone. 📸
- [ ] A fresh install has updates: the run **stops** after `update` with "needs a REBOOT before
      continuing" when the upgrade brought a kernel (Ubuntu also on `/run/reboot-required`). 📸
- [ ] Reboot; `uname -r` is the newest kernel. (No reboot needed: go on to step 3 with this run.)

## Step 3: second run, keys and modules

```bash
ansible-playbook site.yml -K 2>&1 | tee run1.log
```

- [ ] Ends with `failed=0`. The MOK reminder appears once per key: Debian GNOME two (`DKMS`,
      `VirtualBox`), Ubuntu one (`DKMS and VirtualBox`), the KDE VMs one (`VirtualBox`, or `DKMS
      and VirtualBox` on Kubuntu). 📸 the recap and the messages.
- [ ] `sudo mokutil --list-new` lists the pending key(s).
- [ ] Reboot → MokManager → **Enroll MOK** → password (`debian-alpi` / `ubuntu-alpi`) → Reboot.
      Debian GNOME enrolls both keys in one MokManager visit.
- [ ] Keys enrolled: Debian `sudo mokutil --test-key /var/lib/dkms/mok.pub` (GNOME) and
      `.../shim-signed/mok/MOK.der`; Ubuntu and Kubuntu `sudo mokutil --test-key
      /var/lib/shim-signed/mok/MOK.der` → "is already enrolled".
- [ ] VirtualBox under Secure Boot: `lsmod | grep vboxdrv`; `modinfo -F signer vboxdrv` → the
      key's CN; `systemctl is-active vboxdrv`; `id` shows `vboxusers`, `vboxsf` (new login);
      `cat /etc/modprobe.d/alpi-kvm.conf`. A VM starts in VirtualBox inside the VM if nested
      VT-x is on (Debian's 6.12: VirtualBox next to KVM needs the kvm setting). 📸
- [ ] Debian GNOME, NVIDIA: `modinfo -F signer nvidia-current` → `DKMS module signing key`
      (built and signed by DKMS; it does not load without the GPU); `cat
      /etc/modprobe.d/alpi-nvidia.conf` → `options nvidia-current …`; `ls -l
      /etc/modprobe.d/nvidia.conf` → Debian's own, untouched. 📸
- [ ] Ubuntu, NVIDIA: `dpkg -l | grep -E 'linux-modules-nvidia-615-open|nvidia-dkms'` →
      Canonical's modules, no `nvidia-dkms-615-open` package; `modinfo -F signer nvidia` →
      Canonical's key; `cat /etc/modprobe.d/alpi-nvidia.conf` → `options nvidia …`. 📸
- [ ] On a real NVIDIA laptop later: ALPI's options reached the module: `ls /sys/module | grep
      nvidia` (Debian may name it after its renamed file), then that module's
      `parameters/DynamicPowerManagement` → 2.

## Step 4: third run, idempotence

```bash
ansible-playbook site.yml -K 2>&1 | tee run2.log
```

- [ ] `changed=0` in the recap. Anything changed: 📸 the task names (`grep -B1 '^changed' run2.log`).

## Step 5: per role

- [ ] **Hostname:** `hostnamectl` → static and transient hostname are the new name.
- [ ] **Repos:** `ls /etc/apt/sources.list.d/` → `brave-browser-release.sources`,
      `vscode.sources`, `github-cli.sources`, `virtualbox.sources`, each once (VS Code's package
      did not add a second file); `sudo apt-get update` prints no `W:`/`E:` line;
      `dpkg --print-foreign-architectures` → `i386`. 📸
- [ ] **GRUB:** `cat /etc/default/grub.d/99-alpi.cfg`; `ls /etc/default/grub.d/` → ALPI's sorts
      last (Ubuntu's own files before it). At boot the menu **shows** for 5 s (Ubuntu hid it
      before). 📸 (phone photo of the menu).
- [ ] **zram:** `swapon --show` → `/dev/zram0` with priority 100; `cat /proc/sys/vm/swappiness`
      → 180; `dpkg -l systemd-zram-generator`.
- [ ] **Codecs:** Debian `dpkg -l ffmpeg gstreamer1.0-libav libheif-plugin-libde265`; Ubuntu
      `dpkg -l ubuntu-restricted-addons libavcodec-extra`, and no `ttf-mscorefonts-installer`
      (no EULA question appeared). A video plays in the default player.
- [ ] **Steam:** `steam-installer` installed with its i386 libraries; on the NVIDIA VMs (forced
      on) `~/.local/share/applications/steam.desktop` is ALPI's copy (marker on the first line,
      `PrefersNonDefaultGPU=true`, no `env` on the Exec lines), on the KDE VMs none. On a hybrid
      NVIDIA laptop later: Steam from the menu shows up in `nvidia-smi`.
- [ ] **ClamAV:** `systemctl is-active clamav-freshclam` → active.
- [ ] **Flatpaks:** `flatpak list --app` has the defaults (Ubuntu: Chromium among them).
- [ ] **Shell** (new login): `echo $SHELL` → zsh; kali-like-alt prompt; `alias full-update` →
      `sudo apt update && sudo apt full-upgrade -y` and the reboot check; run it once: it
      prints "Reboot needed" only after a kernel upgrade. 📸
- [ ] **Terminal:** Ubuntu: **Ptyxis** opens at 120x35, underline cursor, Fira Code 10, opacity
      0.95. Debian GNOME: gnome-terminal, untouched (no Ptyxis errors in the run). KDE VMs:
      Konsole with the kali-like-alt profile. 📸 each.
- [ ] **Cedilla** (after logout/login): `'` + `c` → `ç` in a text editor and in Brave; the KDE VMs
      (KWin < 6.7): Brave and VS Code started from the menu run on XWayland
      (`xprop` finds their windows). On a pt_BR install: `cat ~/.XCompose | head -3` is the
      pt_BR Compose file (`/etc/default/locale`).
- [ ] **AI tools:** `claude --version`; `ls ~/.local/bin/agy`; the Antigravity IDE starts from the
      menu. Ubuntu: `cat /etc/apparmor.d/alpi-antigravity-ide`; `sudo aa-status | grep
      alpi-antigravity-ide` → loaded; the IDE opens with its sandbox: started from a terminal
      (`~/wks/tools/antigravity/antigravity`) it prints no "The SUID sandbox helper binary was
      found, but is not configured correctly". If it fails, note the mount path it ran from
      (`ls /tmp/.mount_*`): the profile's attachment is `/tmp/.mount_antigr*/antigravity`. 📸
- [ ] **gh reminder:** the run's end printed "The GitHub CLI is not logged in".

## Results

(Notes per step, dated.)

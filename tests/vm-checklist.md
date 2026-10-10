# VM checklist (TODO section 4: "VM with EFI + Secure Boot")

What containers cannot cover: real Secure Boot and MOK enrollment, module builds and signing,
`dracut`, the reboot gate on a real kernel, GRUB, the transient hostname, and desktop sessions.
Two VMs in VirtualBox, both EFI + Secure Boot:

| VM | Like | Covers |
|---|---|---|
| `fedora44-alpi`, Fedora 44 **KDE** | noir | akmods key, `akmod-VirtualBox` signed, NVIDIA akmod build + `dracut` (forced on), Steam launcher, Konsole |
| `el10-alpi`, AlmaLinux 10 **Workstation (GNOME)** | work machine | Oracle VirtualBox's own key, Roboto from upstream, Ptyxis in a real session (AAPI's VM was KDE) |

Tick each step and note any failure under it. Send results as screenshots
(`~/Pictures/Screenshots`); each step says what to capture.

## Step 0: create the VMs (on the host, VirtualBox 7.2)

```bash
mkvm() {  # mkvm <name> <ostype> <iso>
  local VM=$1 DIR="$HOME/VirtualBox VMs/$1"
  VBoxManage createvm --name="$VM" --ostype="$2" --register
  VBoxManage modifyvm "$VM" --memory=8192 --cpus=4 --firmware=efi --graphicscontroller=vmsvga --vram=128 --nic1=nat
  VBoxManage createmedium disk --filename="$DIR/$VM.vdi" --size=61440
  VBoxManage storagectl "$VM" --name=SATA --add=sata --controller=IntelAhci
  VBoxManage storageattach "$VM" --storagectl=SATA --port=0 --device=0 --type=hdd --medium="$DIR/$VM.vdi"
  VBoxManage storageattach "$VM" --storagectl=SATA --port=1 --device=0 --type=dvddrive --medium="$3"
  VBoxManage modifynvram "$VM" inituefivarstore
  VBoxManage modifynvram "$VM" enrollmssignatures
  VBoxManage modifynvram "$VM" enrollorclpk
  VBoxManage modifynvram "$VM" secureboot --enable
}
mkvm fedora44-alpi Fedora_64 "$HOME/Downloads/Fedora-KDE-Desktop-Live-44-x86_64.iso"   # adjust ISO names
mkvm el10-alpi Oracle10_64 "$HOME/Downloads/AlmaLinux-10-latest-x86_64-dvd.iso"
```

- [ ] Install: Fedora KDE live; AlmaLinux with the **Workstation** environment (GNOME). An admin
      user (`wheel`) on both.
- [ ] In each VM: `mokutil --sb-state` → `SecureBoot enabled`; note `hostname` and `uname -r`.
      📸 both.
- [ ] VM off, clean snapshot: `VBoxManage snapshot <vm> take clean`.

## Step 1: bootstrap (both VMs)

```bash
sudo dnf install -y git && git clone https://github.com/phguima/alpi && cd alpi && ./bootstrap.sh
```

- [ ] Installs `ansible-core`, `pciutils`, PyYAML, whiptail and `community.general` (11.x on EL)
      without errors.
- [ ] Asks the hostname (give a **new** one, e.g. `fedora-alpi` / `alma-alpi`) and the git
      identity, then opens the picker: keep the defaults (OK). 📸 the end of the bootstrap output.
- [ ] Fedora only: add `-e is_nvidia=true` to every `ansible-playbook` command below, so the
      NVIDIA path (akmod build, `dracut`, Steam launcher) runs without an NVIDIA GPU. Extra vars
      win over detection. Snapshot first if you want to roll the driver back later.
- [ ] `ansible-playbook site.yml -K --tags resolve` prints the sets; nothing changes. 📸 the
      native/flatpak lists.

## Step 2: first run, the reboot gate

```bash
ansible-playbook site.yml -K 2>&1 | tee run0.log
```

- [ ] A fresh install has updates: the run **stops** after `update` with "needs a REBOOT before
      continuing" (no other role ran). 📸
- [ ] Reboot; `uname -r` is the newest kernel. (If no reboot was needed, it goes straight on: skip
      to step 3 with this run.)

## Step 3: second run, keys and modules

```bash
ansible-playbook site.yml -K 2>&1 | tee run1.log
```

- [ ] Ends with `failed=0`. The MOK reminder appears (Fedora: label `akmods`; EL: the VirtualBox
      key), and on Fedora the NVIDIA "REBOOT is REQUIRED" message. 📸 the recap and the messages.
- [ ] `sudo mokutil --list-new` lists the pending key.
- [ ] Reboot → blue MokManager → **Enroll MOK** → Continue → password (`fedora-alpi` unless you
      changed `mok_password`) → Reboot. 📸 (phone photo) if anything looks off.
- [ ] Key enrolled:
      - Fedora: `sudo mokutil --test-key /etc/pki/akmods/certs/public_key.der` → "is already enrolled".
      - EL: `sudo mokutil --test-key /var/lib/shim-signed/mok/MOK.der` → "is already enrolled".
- [ ] VirtualBox modules load under Secure Boot: `lsmod | grep vboxdrv`; `modinfo -F signer vboxdrv`
      → the akmods key's CN (Fedora) / `<hostname> VirtualBox module signing` (EL);
      `systemctl is-active vboxdrv` (EL); `id` shows `vboxusers` and `vboxsf` (new login). 📸
- [ ] Fedora, NVIDIA: `modinfo -F signer nvidia` → the akmods key's CN (the module is built and
      signed; it does not load, the VM has no NVIDIA GPU); `ls -l /boot/initramfs-$(uname -r).img`
      dated from the run; `cat /etc/modprobe.d/nvidia.conf`. 📸

## Step 4: third run, idempotence

```bash
ansible-playbook site.yml -K 2>&1 | tee run2.log
```

- [ ] `changed=0` in the recap (`grep -A2 'PLAY RECAP' run2.log`). Anything changed: 📸 the task
      names (`grep -B1 '^changed' run2.log`).

## Step 5: per role

- [ ] **Hostname:** `hostnamectl` → static **and** transient hostname are the new name (containers
      can only check the static one). 📸
- [ ] **Repos:** `dnf repolist` → Fedora: `rpmfusion-*`, `brave-browser`, `code`, `gh-cli`,
      `copr:…asus-linux` only if ASUS was detected (should not be); EL: `crb`, `epel`,
      `rpmfusion-*`, `virtualbox`, `brave-browser`, `code`, `gh-cli`. `dnf repolist --enabled |
      grep -i debug` → empty. 📸
- [ ] **Kernels:** `rpm -q kernel-core` → only the running kernel.
- [ ] **GRUB:** `grep -E '^GRUB_(TIMEOUT|TERMINAL_OUTPUT|GFXMODE|GFXPAYLOAD)=' /etc/default/grub`
      → no `GRUB_GFXPAYLOAD`. At boot the menu waits 5 s (Fedora may auto-hide it on a single-OS
      install: hold Shift or press Esc). Press `e` on the default entry → `set gfxpayload=keep`
      is there. 📸 (phone photo of the `e` screen).
- [ ] **Codecs:** `rpm -q ffmpeg` installed, `rpm -q ffmpeg-free` not.
- [ ] **ClamAV:** `systemctl is-active clamav-freshclam` → active.
- [ ] **Flatpaks:** `flatpak list --app` has the defaults (EL also Telegram, Drawy, Inkscape and
      the GNOME ones).
- [ ] **Fonts (EL):** `cat /usr/local/share/fonts/roboto/.version`; `fc-list : family | grep -c '^Roboto'`.
- [ ] **Shell** (new login): `echo $SHELL` → zsh; kali-like-alt prompt; `alias | grep -E
      'full-update|claudecli'`; EL: `full-update` ends with `needs-restarting -r`; Fedora:
      `nvidia-run` alias present. 📸
- [ ] **Terminal:** Fedora: Konsole opens with the kali-like-alt profile. EL: **Ptyxis** opens at
      120x35, underline cursor, Fira Code 10, opacity 0.95. 📸 each.
- [ ] **Cedilla** (after logout/login): `'` + `c` → `ç` in a text editor and in Brave.
- [ ] **Steam (Fedora, NVIDIA forced):** `grep ^Exec ~/.local/share/applications/steam.desktop` →
      every line starts with `env __NV_PRIME_RENDER_OFFLOAD=1 …`.
- [ ] **AI tools:** `claude --version`; `ls ~/.local/bin/agy`; the Antigravity IDE in the menu; `pipx list`
      → markitdown, notebooklm-py, pdf2docx.
- [ ] **gh reminder:** the run's end printed "The GitHub CLI is not logged in"; after
      `gh auth login …` the next run does not.

## Results

(Notes per step, dated.)

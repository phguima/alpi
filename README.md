# ALPI (Ansible Linux Post-Install)

[![Project Status: Active](https://img.shields.io/badge/Project%20Status-Active-brightgreen.svg)](#-project-status)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

ALPI is a single Ansible post-install for Linux workstations. It detects the running distribution and applies the right setup for it. It unifies [AFPI](https://github.com/phguima/afpi) (Fedora) and [AAPI](https://github.com/phguima/aapi) (AlmaLinux 10), and is designed to take in other distributions: Debian 13 and Ubuntu 26.04 are in progress (their first releases wait for test VMs).

## 📊 Project Status

*   **Stage:** parity with AFPI and AAPI reached on October 22, 2026. Ported from AFPI: repositories, the package catalog and picker, codecs, NVIDIA and VirtualBox (with Secure Boot signing), ClamAV, ASUS, Flatpak overrides, hostname, git, zsh, the system update with its reboot gate, kernel maintenance and GRUB settings, the workspace, terminal settings (Konsole, Ptyxis), the cedilla fix (on KDE with KWin older than 6.7, Chromium/Electron apps on XWayland, from AAPI), Python apps (pipx) and the AI tools (Claude Code, Antigravity CLI and IDE). New in ALPI: swap on compressed RAM (zram, on AlmaLinux too), with a reminder when a machine that hibernates has too little disk swap. Ported from AAPI: its AlmaLinux 10 differences (CRB, EPEL, RPM Fusion for EL, Oracle VirtualBox, Flatpaks and Roboto where EL has no package). Validated in Fedora 44 and AlmaLinux 10 containers (Molecule) and on Fedora 44 (GNOME, KDE) and AlmaLinux 10 (GNOME, KDE) VMs with EFI + Secure Boot. The architecture is described in [`PROPOSAL.md`](PROPOSAL.md) and the work plan is in [`TODO.md`](TODO.md).
*   **ALPI replaces AFPI (Fedora) and AAPI (AlmaLinux 10)**, which are frozen.

## 🧭 Design in short

*   **Three independent axes:** distribution (detected), hardware (detected, can be vetoed) and machine/user settings (`host_vars`, never committed). No profiles: each machine picks its own packages.
*   **Package picker:** `pick.py` lists only what the running distro offers (and the running desktop's packages) in groups by purpose (system tools, internet & chat, development…), each row with what it installs, and the zsh aliases with their commands (an alias whose program is unchecked is hidden, and left out if not installed), with the defaults checked, shows the changes before saving, and saves the differences to `host_vars/127.0.0.1/selection.yml`.
*   **Package catalog:** logical package ids mapped to each distribution's package, Flatpak or upstream source, so one list works everywhere.
*   **User customization:** a git-ignored `host_vars/127.0.0.1/custom.yml` adds packages outside the catalog, uninstalls and vetoes hardware features, so `git pull` never conflicts with local changes.
*   **Explicit support matrix:** the playbook stops right away on an unsupported distribution or version.

## 🚀 Usage

```bash
git clone https://github.com/phguima/alpi && cd alpi
./update.sh                                      # the latest release (run it again before each update)
./bootstrap.sh                                   # installs Ansible, asks hostname/git identity, runs the picker
./pick.py                                        # optional: change the package/feature choice later
cp custom.yml.example host_vars/127.0.0.1/custom.yml   # optional: packages outside the catalog, vetoes
ansible-playbook site.yml -K --tags resolve      # preview: prints what would be installed
ansible-playbook site.yml -K
```

### Releases

Real machines run releases: `v*` tags, each cut from `main` after the full test suite passes. `./update.sh` puts the clone on the newest one; `./update.sh main` follows the development line instead (the latest commits, tested in containers but not yet released). Your settings in `host_vars/` are git-ignored, so switching keeps them.

## 🔐 API keys (optional)

ALPI needs no secrets and no vault. To have API keys exported in your `~/.zshrc` (never root's), keep them in an encrypted **Ansible Vault**, which is git-ignored and never committed:

```bash
ansible-vault create group_vars/all/secrets.yml
```

with content like:

```yaml
api_keys: |
  export SERVICE_API_KEY="your_value_here"
```

Then add `--ask-vault-pass` to the `ansible-playbook` commands (`./bootstrap.sh` reminds you when the vault exists). Use `ansible-vault edit group_vars/all/secrets.yml` to change it later. While `api_keys` is unset or empty, the block is removed from `~/.zshrc`.

## 🧪 Tests

Every change ships with tests. [Molecule](https://ansible.readthedocs.io/projects/molecule/) runs the playbook in podman containers (never on the host); pytest covers the filter plugin and the picker. `tests/run.sh` runs them one scenario at a time and prints a timed summary; package downloads are cached in podman volumes (`alpi-dnf-*`) and Ansible collections in `~/.cache/alpi-molecule`, so only the first run downloads everything.

```bash
pipx install molecule && pipx inject molecule 'molecule-plugins[podman]' pytest
ansible-galaxy collection install containers.podman
tests/run.sh quick                        # pytest + scenarios without real installs (a few minutes)
tests/run.sh full                         # every scenario, before a commit
tests/run.sh el10-work                    # just the named scenarios
```

## ⚖️ License

GPL-3.0. See [LICENSE](LICENSE).

# ALPI (Ansible Linux Post-Install)

[![Project Status: Porting](https://img.shields.io/badge/Project%20Status-Porting-yellow.svg)](#-project-status)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

ALPI is a single Ansible post-install for Linux workstations. It detects the running distribution and applies the right setup for it. It unifies [AFPI](https://github.com/phguima/afpi) (Fedora) and [AAPI](https://github.com/phguima/aapi) (AlmaLinux 10), and is designed to take in other distributions (Debian, Ubuntu…) later.

## 📊 Project Status

*   **Stage:** porting. Ported from AFPI so far: repositories, the package catalog and picker, codecs, NVIDIA and VirtualBox (with Secure Boot signing), ClamAV, ASUS, Flatpak overrides, hostname, git, zsh, the system update with its reboot gate, kernel maintenance and GRUB settings, the workspace, terminal settings (Konsole, Ptyxis), the cedilla fix, Python apps (pipx) and the AI tools (Claude Code, Antigravity CLI and IDE). Still to port: the Steam shortcut on the NVIDIA GPU, then AAPI's AlmaLinux 10 differences and parity checks on a VM. Validated in Fedora 44 and AlmaLinux 10 containers. The architecture is described in [`PROPOSAL.md`](PROPOSAL.md) and the work plan is in [`TODO.md`](TODO.md).
*   **Until parity is reached, use AFPI (Fedora) or AAPI (AlmaLinux 10).**

## 🧭 Design in short

*   **Three independent axes:** distribution (detected), hardware (detected, can be vetoed) and machine/user settings (`host_vars`, never committed). No profiles: each machine picks its own packages.
*   **Package picker:** `pick.py` lists only what the running distro offers (and the running desktop's packages), with the defaults checked, and saves the differences to `host_vars/127.0.0.1/selection.yml`.
*   **Package catalog:** logical package ids mapped to each distribution's package, Flatpak or upstream source, so one list works everywhere.
*   **User customization:** a git-ignored `host_vars/127.0.0.1/custom.yml` adds packages outside the catalog, uninstalls and vetoes hardware features, so `git pull` never conflicts with local changes.
*   **Explicit support matrix:** the playbook stops right away on an unsupported distribution or version.

## 🚀 Usage

```bash
./bootstrap.sh                                   # installs Ansible, asks hostname/git identity, runs the picker
./pick.py                                        # optional: change the package/feature choice later
cp custom.yml.example host_vars/127.0.0.1/custom.yml   # optional: packages outside the catalog, vetoes
ansible-playbook site.yml -K --tags resolve      # preview: prints what would be installed
ansible-playbook site.yml -K
```

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

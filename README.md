# ALPI (Ansible Linux Post-Install)

[![Project Status: Design](https://img.shields.io/badge/Project%20Status-Design-yellow.svg)](#-project-status)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

ALPI is a single Ansible post-install for Linux workstations. It detects the running distribution and applies the right setup for it. It unifies [AFPI](https://github.com/phguima/afpi) (Fedora) and [AAPI](https://github.com/phguima/aapi) (AlmaLinux 10), and is designed to take in other distributions (Debian, Ubuntu…) later.

## 📊 Project Status

*   **Stage:** skeleton. Distro detection, profiles, the package catalog and user customization work (validated on Fedora 44 and AlmaLinux 10 containers); the roles from AFPI/AAPI are not ported yet. The architecture is described in [`PROPOSAL.md`](PROPOSAL.md) and the work plan is in [`TODO.md`](TODO.md).
*   **Until parity is reached, use AFPI (Fedora) or AAPI (AlmaLinux 10).**

## 🧭 Design in short

*   **Three independent axes:** distribution (detected), hardware (detected, can be vetoed) and machine/user settings (`host_vars`, never committed). A small **profile** (`personal`, `work`) carries policy only.
*   **Package catalog:** logical package ids mapped to each distribution's package, Flatpak or upstream source, so one list works everywhere.
*   **User customization:** a git-ignored `host_vars/127.0.0.1/custom.yml` toggles features and adds or skips packages, so `git pull` never conflicts with local changes.
*   **Explicit support matrix:** the playbook stops right away on an unsupported distribution or version.

## 🚀 Usage (skeleton)

```bash
./bootstrap.sh                                   # installs Ansible, asks profile/hostname/git identity
cp custom.yml.example host_vars/127.0.0.1/custom.yml   # optional: your packages and features
ansible-playbook site.yml -K --tags resolve      # preview: prints what would be installed
ansible-playbook site.yml -K
```

## 🧪 Tests

Every change ships with tests. [Molecule](https://ansible.readthedocs.io/projects/molecule/) runs the playbook in podman containers (never on the host); pytest covers the filter plugin.

```bash
pipx install molecule && pipx inject molecule 'molecule-plugins[podman]' pytest
ansible-galaxy collection install containers.podman
molecule test --all                       # fedora44-personal, el10-work, failures, unsupported, bootstrap
~/.local/share/pipx/venvs/molecule/bin/python -m pytest -q tests/unit
```

## ⚖️ License

GPL-3.0. See [LICENSE](LICENSE).

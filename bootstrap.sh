#!/bin/bash

# ALPI (Ansible Linux Post-Install) Bootstrap Script
# Installs Ansible for the running distro, asks the per-machine settings (hostname, git identity)
# and runs the package picker (pick.py), so ansible-playbook never stops for input.

set -e

C_RESET='\033[0m'
C_BLUE='\033[1;34m'
C_GREEN='\033[1;32m'
C_YELLOW='\033[1;33m'
C_RED='\033[1;31m'

prompt() { echo -e "${C_BLUE}==>${C_RESET} $1"; }
success() { echo -e "${C_GREEN}SUCCESS:${C_RESET} $1"; }
warn() { echo -e "${C_YELLOW}WARNING:${C_RESET} $1"; }
error() { echo -e "${C_RED}ERROR:${C_RESET} $1"; }

if [ ! -f "site.yml" ] || [ ! -d "group_vars/all" ]; then
    error "Run this script from the root of the alpi project."
    exit 1
fi

# 1. Distro: only what the package manager step needs. The playbook's support matrix
#    (group_vars/all/support.yml) is the authoritative check.
. /etc/os-release
case "$ID" in
    fedora|almalinux)
        # ansible-core everywhere (EL10 has no full 'ansible' package); pciutils for GPU detection;
        # newt for whiptail (pick.py)
        prompt "Installing ansible-core, pciutils, PyYAML and whiptail ($PRETTY_NAME)..."
        sudo dnf install -y ansible-core pciutils python3-pyyaml newt
        ;;
    *)
        error "$PRETTY_NAME is not supported (yet). See group_vars/all/support.yml."
        exit 1
        ;;
esac

# 2. Collections, pinned to what the installed ansible-core supports:
#    community.general 12.x needs ansible-core 2.17+, and EL10 ships 2.16.
core_version=$(python3 -c 'from ansible.release import __version__ as v; print(v)')
if python3 -c 'import sys; v = tuple(map(int, sys.argv[1].split(".")[:2])); sys.exit(0 if v >= (2, 17) else 1)' "$core_version"; then
    cg_spec='community.general'
else
    cg_spec='community.general:>=11.0.0,<12.0.0'
fi
prompt "Installing ${cg_spec} for ansible-core ${core_version}..."
ansible-galaxy collection install "$cg_spec"

# 3. Machine settings. Answers go to host_vars/127.0.0.1/bootstrap.yml (git-ignored), rewritten
#    with PyYAML so names with quotes survive; other keys in it are kept. Hand-written settings
#    belong in host_vars/127.0.0.1/custom.yml, which this script never touches.
HOST_VARS_DIR="host_vars/127.0.0.1"
HOST_VARS="$HOST_VARS_DIR/bootstrap.yml"
mkdir -p "$HOST_VARS_DIR"

# AFPI/AAPI kept these settings in host_vars/127.0.0.1.yml: move it into the directory.
if [ -f "host_vars/127.0.0.1.yml" ] && [ ! -f "$HOST_VARS" ]; then
    mv "host_vars/127.0.0.1.yml" "$HOST_VARS"
    success "Moved host_vars/127.0.0.1.yml to ${HOST_VARS}."
fi

# Prints the value of key $1 from YAML file $2 (empty when missing)
yaml_get() {
    [ -f "$2" ] || return 0
    python3 -c 'import sys, yaml; v = (yaml.safe_load(open(sys.argv[1])) or {}).get(sys.argv[2]); print(v if v is not None else "")' \
        "$2" "$1"
}

# ask VAR "Label" default: reads into VAR, Enter keeps the default
ask() {
    local answer
    read -r -p "$(echo -e "${C_BLUE}==>${C_RESET} $2 [$3]: ")" answer
    printf -v "$1" '%s' "${answer:-$3}"
}

new_hostname="" git_name="" git_email=""  # set by ask()
if [ -t 0 ]; then
    # Empty leaves the hostname alone (a work machine named by IT); '-' forgets a saved one.
    current_hostname=$(hostnamectl hostname 2>/dev/null || true)
    current_hostname="${current_hostname:-$HOSTNAME}"
    saved_hostname=$(yaml_get system_hostname "$HOST_VARS")
    while true; do
        ask new_hostname "Hostname (now '${current_hostname}'; empty: leave it as it is, '-': forget the saved one)" "$saved_hostname"
        [ "$new_hostname" = "-" ] && new_hostname="" && break
        # RFC 1123 label: letters, digits and '-', 1-63 chars, no leading/trailing '-'
        if [ -z "$new_hostname" ] || [[ "$new_hostname" =~ ^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$ ]]; then
            break
        fi
        error "Invalid hostname '${new_hostname}': use letters, digits and '-' (max 63 chars)."
    done

    # Git identity: defaults to what was saved before, then to the current ~/.gitconfig.
    # Leaving both empty means the playbook does not touch user.name/user.email.
    saved_git_name=$(yaml_get git_user_name "$HOST_VARS")
    saved_git_email=$(yaml_get git_user_email "$HOST_VARS")
    ask git_name "Git user.name (empty to skip)" "${saved_git_name:-$(git config --global user.name 2>/dev/null || true)}"
    while true; do
        ask git_email "Git user.email (empty to skip)" "${saved_git_email:-$(git config --global user.email 2>/dev/null || true)}"
        if [ -z "$git_email" ] || [[ "$git_email" =~ ^[^[:space:]@]+@[^[:space:]@]+$ ]]; then
            break
        fi
        error "Invalid e-mail '${git_email}'."
    done

    python3 - "$HOST_VARS" "$new_hostname" "$git_name" "$git_email" <<'PY'
import os, sys, yaml
path, hostname, name, email = sys.argv[1:]
data = {}
if os.path.exists(path):
    with open(path) as f:
        data = yaml.safe_load(f) or {}
data.pop("alpi_profile", None)  # profiles were replaced by pick.py (2026-10-08)
data.update({"git_user_name": name, "git_user_email": email})
if hostname:
    data["system_hostname"] = hostname
else:
    data.pop("system_hostname", None)
with open(path, "w") as f:
    f.write("---\n# Written by bootstrap.sh: settings for this machine only (not tracked by git).\n")
    f.write("# Hand-written settings go in custom.yml next to this file (see custom.yml.example).\n")
    yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True, default_flow_style=False)
PY
    success "Settings saved to ${HOST_VARS}."

    # 4. Packages and features: only what this distro offers; saved to selection.yml
    python3 pick.py
else
    warn "No terminal: settings and packages not asked. The playbook uses ${HOST_VARS_DIR}/ if it exists."
fi

if [ ! -f "$HOST_VARS_DIR/custom.yml" ]; then
    prompt "Packages outside the catalog, uninstalls or hardware vetoes go in a custom.yml:"
    echo -e "      ${C_YELLOW}cp custom.yml.example ${HOST_VARS_DIR}/custom.yml${C_RESET}"
fi

# 5. Optional vault (API keys)
VAULT_FLAG=""
if [ -f "group_vars/all/secrets.yml" ]; then
    if grep -q "\$ANSIBLE_VAULT" "group_vars/all/secrets.yml"; then
        VAULT_FLAG=" --ask-vault-pass"
    else
        warn "Note: 'group_vars/all/secrets.yml' is NOT encrypted. Consider running:"
        echo -e "      ${C_YELLOW}ansible-vault encrypt group_vars/all/secrets.yml${C_RESET}"
    fi
fi

# 6. Final instructions
echo ""
prompt "Bootstrap complete! Preview what will be installed (changes nothing):"
echo -e "${C_GREEN}ansible-playbook site.yml -K --tags resolve${VAULT_FLAG}${C_RESET}"
prompt "Change the package choice later with ./pick.py. Then run the full playbook:"
echo -e "${C_GREEN}ansible-playbook site.yml -K${VAULT_FLAG}${C_RESET}"

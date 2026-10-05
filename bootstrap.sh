#!/bin/bash

# ALPI (Ansible Linux Post-Install) Bootstrap Script
# Installs Ansible for the running distro and asks the per-machine settings (profile, hostname,
# git identity), so ansible-playbook never stops for input.

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
        # ansible-core everywhere (EL10 has no full 'ansible' package); pciutils for GPU detection
        prompt "Installing ansible-core, pciutils and PyYAML ($PRETTY_NAME)..."
        sudo dnf install -y ansible-core pciutils python3-pyyaml
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

profiles=$(python3 -c 'import yaml; print(" ".join(yaml.safe_load(open("group_vars/all/support.yml"))["alpi_profiles"]))')
profile="" new_hostname="" git_name="" git_email=""  # set by ask()
if [ -t 0 ]; then
    saved_profile=$(yaml_get alpi_profile "$HOST_VARS")
    while true; do
        ask profile "Profile (${profiles// /, })" "${saved_profile:-personal}"
        [[ " $profiles " == *" $profile "* ]] && break
        error "Unknown profile '${profile}'."
    done

    # The profile decides whether the hostname is managed (group_vars/profile_*/main.yml)
    if [ "$(yaml_get alpi_manage_hostname "group_vars/profile_${profile}/main.yml")" = "True" ]; then
        current_hostname=$(hostnamectl hostname 2>/dev/null || true)
        current_hostname="${current_hostname:-$HOSTNAME}"
        saved_hostname=$(yaml_get system_hostname "$HOST_VARS")
        while true; do
            ask new_hostname "Hostname" "${saved_hostname:-$current_hostname}"
            # RFC 1123 label: letters, digits and '-', 1-63 chars, no leading/trailing '-'
            if [[ "$new_hostname" =~ ^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$ ]]; then
                break
            fi
            error "Invalid hostname '${new_hostname}': use letters, digits and '-' (max 63 chars)."
        done
    fi

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

    python3 - "$HOST_VARS" "$profile" "$new_hostname" "$git_name" "$git_email" <<'PY'
import os, sys, yaml
path, profile, hostname, name, email = sys.argv[1:]
data = {}
if os.path.exists(path):
    with open(path) as f:
        data = yaml.safe_load(f) or {}
data.update({"alpi_profile": profile, "git_user_name": name, "git_user_email": email})
if hostname:
    data["system_hostname"] = hostname
else:
    data.pop("system_hostname", None)
with open(path, "w") as f:
    f.write("---\n# Written by bootstrap.sh: settings for this machine only (not tracked by git).\n")
    f.write("# Hand-written settings go in custom.yml next to this file (see custom.yml.example).\n")
    yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True, default_flow_style=False)
PY
    success "Settings saved to ${HOST_VARS} (profile '${profile}')."
else
    warn "No terminal: settings not asked. The playbook uses ${HOST_VARS} if it exists."
fi

if [ ! -f "$HOST_VARS_DIR/custom.yml" ]; then
    warn "No ${HOST_VARS_DIR}/custom.yml: repository defaults only. To customize packages and features:"
    echo -e "      ${C_YELLOW}cp custom.yml.example ${HOST_VARS_DIR}/custom.yml${C_RESET}"
fi

# 4. Optional vault (API keys)
VAULT_FLAG=""
if [ -f "group_vars/all/secrets.yml" ]; then
    if grep -q "\$ANSIBLE_VAULT" "group_vars/all/secrets.yml"; then
        VAULT_FLAG=" --ask-vault-pass"
    else
        warn "Note: 'group_vars/all/secrets.yml' is NOT encrypted. Consider running:"
        echo -e "      ${C_YELLOW}ansible-vault encrypt group_vars/all/secrets.yml${C_RESET}"
    fi
fi

# 5. Final instructions
echo ""
prompt "Bootstrap complete! Preview what will be installed (changes nothing):"
echo -e "${C_GREEN}ansible-playbook site.yml -K --tags resolve${VAULT_FLAG}${C_RESET}"
prompt "Then run the full playbook:"
echo -e "${C_GREEN}ansible-playbook site.yml -K${VAULT_FLAG}${C_RESET}"

#!/bin/bash
# Stand-in for https://claude.ai/install.sh (served by prepare.yml): installs a fake launcher in
# ~/.local/bin and logs each run. Stricter than the real one, which refuses root only under sudo:
# here any root run fails, so the role must run it as the user with the user's HOME.
set -e
[ "$(id -u)" -ne 0 ] || { echo "stand-in: run as the user, not root" >&2; exit 1; }
[ "$HOME" = "$(getent passwd "$(id -un)" | cut -d: -f6)" ] || { echo "stand-in: HOME is $HOME" >&2; exit 1; }
mkdir -p "$HOME/.local/bin"
printf '#!/bin/sh\necho "claude stand-in"\n' > "$HOME/.local/bin/claude"
chmod +x "$HOME/.local/bin/claude"
echo run >> "$HOME/.alpi-installs-claude"

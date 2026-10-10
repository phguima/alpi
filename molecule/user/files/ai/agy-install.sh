#!/bin/bash
# Stand-in for https://antigravity.google/cli/install.sh (served by prepare.yml): installs a fake
# ~/.local/bin/agy and logs each run. Its shell setup ('agy install') does what AFPI saw the real
# one do to ~/.zshrc: it deletes 'alias antigravity=' lines (hence the alias antigravity-ide).
set -e
[ "$(id -u)" -ne 0 ] || { echo "stand-in: run as the user, not root" >&2; exit 1; }
[ "$HOME" = "$(getent passwd "$(id -un)" | cut -d: -f6)" ] || { echo "stand-in: HOME is $HOME" >&2; exit 1; }
mkdir -p "$HOME/.local/bin"
printf '#!/bin/sh\necho "agy stand-in"\n' > "$HOME/.local/bin/agy"
chmod +x "$HOME/.local/bin/agy"
[ ! -f "$HOME/.zshrc" ] || sed -i '/^alias antigravity=/d' "$HOME/.zshrc"
echo run >> "$HOME/.alpi-installs-agy"

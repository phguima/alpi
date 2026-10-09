#!/bin/bash
# Runs the tests: pytest, then Molecule scenarios one at a time, so one failure (e.g. a network
# outage) does not stop the rest. Logs go to ~/.cache/alpi-molecule/logs/<scenario>.log; the
# summary lists each scenario's result.
#   tests/run.sh quick        while working: no real installs (a few minutes)
#   tests/run.sh full         before a commit: every scenario
#   tests/run.sh <scenario>…  just those
# Package downloads are cached in per-container podman volumes (alpi-dnf-*) and collections in
# ~/.cache/alpi-molecule/collections. Clean up with:
#   podman volume rm $(podman volume ls -q --filter name=alpi-dnf-); rm -rf ~/.cache/alpi-molecule

set -u
cd "$(dirname "$0")/.." || exit 1

QUICK=(catalog failures services asus secureboot common unsupported boot)
FULL=(catalog failures services asus secureboot common unsupported update boot el10-work fedora44-personal bootstrap)

case "${1:-quick}" in
    quick) scenarios=("${QUICK[@]}") ;;
    full)  scenarios=("${FULL[@]}") ;;
    *)     scenarios=("$@") ;;
esac

PYTHON=~/.local/share/pipx/venvs/molecule/bin/python
# Molecule runs the first ansible-playbook in PATH. The venv's own ansible-core (a Molecule
# dependency) comes first, so every machine tests with the same recent controller: EL10's system
# ansible-core 2.16 has dnf5 bugs (no install by URL, no libdnf5 in Fedora's bare image) that a
# real Fedora run, with Fedora's own ansible-core, never meets.
export PATH="$(dirname "$PYTHON"):$PATH"
LOGS=~/.cache/alpi-molecule/logs
mkdir -p "$LOGS"

results=()
failed=0
start_all=$SECONDS

echo "==> pytest"
if "$PYTHON" -m pytest -q tests/unit; then results+=("pytest: ok"); else results+=("pytest: FAILED"); failed=1; fi

for s in "${scenarios[@]}"; do
    echo "==> molecule test -s $s (log: $LOGS/$s.log)"
    start=$SECONDS
    # Piped: Ansible refuses to run with non-blocking stdio in some terminals/harnesses.
    molecule test -s "$s" 2>&1 | cat > "$LOGS/$s.log"
    rc=${PIPESTATUS[0]}
    # Molecule's SCENARIO RECAP can say failed=0 after a failed step it cleaned up after; the exit
    # code and these lines are what count.
    if grep -qE 'Executed: Failed' "$LOGS/$s.log"; then rc=1; fi
    took=$(( (SECONDS - start) / 60 ))m$(( (SECONDS - start) % 60 ))s
    if [ "$rc" -eq 0 ]; then
        results+=("$s: ok ($took)")
    else
        results+=("$s: FAILED ($took), see $LOGS/$s.log")
        failed=1
    fi
    echo "    ${results[-1]}"
done

echo
echo "==> Summary ($(( (SECONDS - start_all) / 60 )) min)"
printf '    %s\n' "${results[@]}"
exit "$failed"

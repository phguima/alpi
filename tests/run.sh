#!/bin/bash
# Runs the tests: pytest, then the Molecule scenarios, ALPI_JOBS at a time (default 4; 1 runs them
# one by one), so one failure (e.g. a network outage) does not stop the rest. Scenarios share
# nothing: their own containers, dnf cache volumes and network namespaces (the stand-in servers on
# 127.0.0.1 do not clash). Logs go to ~/.cache/alpi-molecule/logs/<scenario>.log; the summary
# lists each scenario's result.
#   tests/run.sh quick        while working: no real installs (a few minutes)
#   tests/run.sh full         before a commit: every scenario
#   tests/run.sh apt          the scenarios with a Debian or Ubuntu instance
#   tests/run.sh <scenario>…  just those
#   ALPI_JOBS=1 tests/run.sh  one at a time
# Package downloads are cached in per-container podman volumes (alpi-dnf-*) and collections in
# ~/.cache/alpi-molecule/collections. Clean up with:
#   podman volume rm $(podman volume ls -q --filter name=alpi-dnf-); rm -rf ~/.cache/alpi-molecule

set -u
cd "$(dirname "$0")/.." || exit 1

# Longest first (times of the 2026-10-23 full run), so a long one does not start last
QUICK=(user failures catalog secureboot memory upstream boot flags asus common services debian13 ubuntu2604
       unsupported)
FULL=(debian13-personal ubuntu2604-personal user el10-work bootstrap fedora44-personal failures catalog update
      secureboot memory upstream ubuntu2604 boot flags asus common services debian13 unsupported)
# Every scenario with an apt instance (Debian 13, Ubuntu 26.04), for work on the apt code paths
APT=(debian13-personal ubuntu2604-personal user bootstrap failures update secureboot memory ubuntu2604 boot
     services debian13 unsupported)
JOBS=${ALPI_JOBS:-4}

case "${1:-quick}" in
    quick) scenarios=("${QUICK[@]}") ;;
    full)  scenarios=("${FULL[@]}") ;;
    apt)   scenarios=("${APT[@]}") ;;
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

# One scenario: its log, then a one-line result in $LOGS/<scenario>.result
run_scenario() {
    local s=$1 start=$SECONDS rc took
    # Piped: Ansible refuses to run with non-blocking stdio in some terminals/harnesses.
    molecule test -s "$s" 2>&1 | cat > "$LOGS/$s.log"
    rc=${PIPESTATUS[0]}
    # Molecule's SCENARIO RECAP can say failed=0 after a failed step it cleaned up after; the exit
    # code and these lines are what count.
    if grep -qE 'Executed: Failed' "$LOGS/$s.log"; then rc=1; fi
    took=$(( (SECONDS - start) / 60 ))m$(( (SECONDS - start) % 60 ))s
    if [ "$rc" -eq 0 ]; then
        echo "$s: ok ($took)" > "$LOGS/$s.result"
    else
        echo "$s: FAILED ($took), see $LOGS/$s.log" > "$LOGS/$s.result"
    fi
    echo "    $(cat "$LOGS/$s.result")"
}

for s in "${scenarios[@]}"; do
    rm -f "$LOGS/$s.result"
    while [ "$(jobs -rp | wc -l)" -ge "$JOBS" ]; do wait -n; done
    echo "==> molecule test -s $s (log: $LOGS/$s.log)"
    run_scenario "$s" &
done
wait

for s in "${scenarios[@]}"; do
    r=$(cat "$LOGS/$s.result" 2>/dev/null || echo "$s: FAILED (no result), see $LOGS/$s.log")
    results+=("$r")
    case $r in *FAILED*) failed=1 ;; esac
done

echo
echo "==> Summary ($(( (SECONDS - start_all) / 60 )) min)"
printf '    %s\n' "${results[@]}"
exit "$failed"

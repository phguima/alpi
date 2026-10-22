#!/bin/bash

# ALPI update: puts this clone on the latest release (the newest v* tag), the tested snapshot
# real machines should run. './update.sh main' follows the development line instead (main, with
# its latest commits). Run it before ./bootstrap.sh on a new machine and before each playbook
# run. The settings in host_vars/ are git-ignored, so switching never touches them.

set -e

C_RESET='\033[0m'
C_BLUE='\033[1;34m'
C_RED='\033[1;31m'

prompt() { echo -e "${C_BLUE}==>${C_RESET} $1"; }
error() { echo -e "${C_RED}ERROR:${C_RESET} $1"; }

if [ ! -f "site.yml" ] || [ ! -d "group_vars/all" ]; then
    error "Run this script from the root of the alpi project."
    exit 1
fi

case "${1:-release}" in
    release|main) ;;
    *) error "Usage: ./update.sh [main]"; exit 1 ;;
esac

git fetch --quiet --tags origin

if [ "${1:-release}" = main ]; then
    git checkout --quiet main
    git pull --quiet --ff-only
    prompt "On main ($(git log -1 --format='%h %s')): the development line, not a release."
    exit 0
fi

latest=$(git tag --list 'v*' --sort=-v:refname | head -n 1)
if [ -z "$latest" ]; then
    error "No release yet. Use './update.sh main'."
    exit 1
fi
git -c advice.detachedHead=false checkout --quiet "$latest"
prompt "On release $latest. './update.sh main' follows the latest commits instead."

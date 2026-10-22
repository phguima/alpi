"""Unit tests for update.sh, against throwaway git repositories (an 'origin' and a clone of it)
in tmp_path. Nothing touches the real clone."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


def commit(repo, message):
    (repo / "log.txt").open("a").write(message + "\n")
    git(repo, "add", "log.txt")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repos(tmp_path):
    """(origin, clone): origin has the project's markers, update.sh and one commit on main."""
    origin = tmp_path / "origin"
    origin.mkdir()
    git(origin, "init", "-q", "-b", "main")
    (origin / "site.yml").write_text("---\n")
    (origin / "group_vars" / "all").mkdir(parents=True)
    (origin / "group_vars" / "all" / ".keep").write_text("")
    (origin / ".gitignore").write_text("host_vars/\n")
    shutil.copy(ROOT / "update.sh", origin / "update.sh")
    git(origin, "add", ".")
    commit(origin, "first")
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", str(origin), str(clone))
    return origin, clone


def update(clone, *args):
    return subprocess.run(["./update.sh", *args], cwd=clone, capture_output=True, text=True)


def test_goes_to_the_newest_release_by_version(repos):
    origin, clone = repos
    tagged = {}
    for tag in ("v1.2.0", "v1.10.0", "v1.9.0"):
        tagged[tag] = commit(origin, tag)
        git(origin, "tag", tag)
    commit(origin, "after the last release")
    r = update(clone)
    assert r.returncode == 0, r.stderr
    assert git(clone, "rev-parse", "HEAD") == tagged["v1.10.0"]
    assert "On release v1.10.0" in r.stdout


def test_main_follows_the_latest_commit_and_comes_back_from_a_release(repos):
    origin, clone = repos
    commit(origin, "release")
    git(origin, "tag", "v1.0.0")
    head = commit(origin, "newer")
    assert update(clone).returncode == 0
    r = update(clone, "main")
    assert r.returncode == 0, r.stderr
    assert git(clone, "rev-parse", "HEAD") == head
    assert git(clone, "branch", "--show-current") == "main"


def test_settings_survive_the_switch(repos):
    origin, clone = repos
    commit(origin, "release")
    git(origin, "tag", "v1.0.0")
    settings = clone / "host_vars" / "127.0.0.1" / "custom.yml"
    settings.parent.mkdir(parents=True)
    settings.write_text("packages_add: [gimp]\n")
    assert update(clone).returncode == 0
    assert update(clone, "main").returncode == 0
    assert settings.read_text() == "packages_add: [gimp]\n"


def test_without_a_release_it_says_to_use_main(repos):
    _, clone = repos
    r = update(clone)
    assert r.returncode == 1
    assert "No release yet" in r.stdout


def test_rejects_an_unknown_argument(repos):
    _, clone = repos
    r = update(clone, "prod")
    assert r.returncode == 1
    assert "Usage" in r.stdout

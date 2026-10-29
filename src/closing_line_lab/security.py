"""Value patterns supplement the owner's mandatory legacy scan; matches stay private."""

import re
import subprocess

from .common import ROOT

PATTERNS = [
    r"nvapi-[A-Za-z0-9_-]{10,}",
    "KGA" + r"T_[A-Za-z0-9_-]{10,}",
    r"sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}",
    r"gh[opusr]_[A-Za-z0-9]{30,}",
    r"github_pat_[A-Za-z0-9_]{30,}",
    r"(?:AKIA|ASIA)[A-Z0-9]{16}",
    r"AIza[A-Za-z0-9_-]{35}",
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
]


def check_values(payload):
    text = payload.decode("utf-8", errors="ignore") if isinstance(payload, bytes) else payload
    if any(re.search(pattern, text) for pattern in PATTERNS):
        raise RuntimeError("Credential value pattern detected; no matched value printed")


def publication_scan():
    legacy = subprocess.run(
        ["git", "grep", "-nE", r"nvapi-[A-Za-z0-9]{10}|" + "KGA" + r'T_|"key"\s*:'],
        cwd=ROOT,
        capture_output=True,
    )
    if legacy.returncode != 1:
        raise RuntimeError("Mandatory legacy secret scan matched or failed")
    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0")
    for path in filter(None, paths):
        check_values(subprocess.check_output(["git", "show", b":" + path], cwd=ROOT))
    return {
        "status": "CLEAN",
        "scope": "staged tracked blobs plus mandatory legacy working-tree scan",
    }


def history_scan():
    objects = subprocess.check_output(["git", "rev-list", "--objects", "--all"], cwd=ROOT)
    ids = [line.split(b" ", 1)[0] for line in objects.splitlines()]
    payload = subprocess.check_output(
        ["git", "cat-file", "--batch"], input=b"\n".join(ids) + b"\n", cwd=ROOT
    )
    offset, blobs = 0, 0
    while offset < len(payload):
        end = payload.index(b"\n", offset)
        _, kind, size = payload[offset:end].split()
        size = int(size)
        content = payload[end + 1 : end + 1 + size]
        if kind == b"blob":
            check_values(content)
            blobs += 1
        offset = end + 2 + size
    return {"status": "CLEAN", "scope": "all reachable Git blob contents", "blobs": blobs}

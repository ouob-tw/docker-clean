"""QA-owned disposable-daemon fixtures. Never accepts a host daemon target."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import uuid

QA_ROOT = Path('/tmp/docker-clean-qa-toga-20260921')
SOCKET = QA_ROOT / 'socket/docker.sock'
CONTAINER_NAME = 'docker-clean-qa-toga-20260921'


def docker(*args: str, check: bool = True, input: str | None = None):
    return subprocess.run(
        ['docker', '--host', f'unix://{SOCKET}', *args],
        text=True, capture_output=True, check=check, input=input,
        env={**os.environ, 'DOCKER_CONTEXT': '', 'DOCKER_HOST': f'unix://{SOCKET}'},
    )


def guard():
    assert str(SOCKET).startswith('/tmp/docker-clean-qa-toga-20260921/')
    name = docker('info', '--format', '{{.Name}}').stdout.strip()
    expected = subprocess.run(
        ['docker', '--host', 'unix:///var/run/docker.sock', 'inspect',
         '--format', '{{.Config.Hostname}}', CONTAINER_NAME],
        text=True, capture_output=True, check=True,
    ).stdout.strip()
    assert name == expected, f'Refuse unrecognized daemon: {name}'


def image(name: str, *aliases: str) -> str:
    """Make a unique image from the QA busybox base without building on host."""
    guard()
    container = docker('create', '--label', 'docker-clean.qa=fixture',
                       'busybox:1.37', 'true').stdout.strip()
    try:
        identifier = docker('commit', '--change', f'LABEL qa.nonce={uuid.uuid4()}',
                            container, name).stdout.strip()
    finally:
        docker('rm', container)
    for alias in aliases:
        docker('tag', identifier, alias)
    return identifier


def containers():
    identifiers = docker('ps', '-aq').stdout.split()
    if not identifiers:
        return []
    return json.loads(docker('inspect', *identifiers).stdout)


if __name__ == '__main__':
    guard()
    print(docker('info', '--format', '{{.ID}} {{.Name}} {{.Driver}}').stdout.strip())

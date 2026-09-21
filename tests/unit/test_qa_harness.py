"""Mocked QA boundary regressions; these do not constitute Docker E2E evidence."""
import importlib
from pathlib import Path
import subprocess

import pytest


@pytest.fixture
def harness(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'qa_e2e'))
    return importlib.import_module('run_cli')


def test_exists_does_not_treat_permission_denied_as_missing(harness, monkeypatch):
    def denied(args, **kwargs):
        if kwargs.get('check'):
            raise subprocess.CalledProcessError(1, args, stderr='permission denied')
        return subprocess.CompletedProcess(args, 1, stdout='', stderr='permission denied')

    monkeypatch.setattr(subprocess, 'run', denied)
    with pytest.raises(subprocess.CalledProcessError, match='returned non-zero'):
        harness.exists('sha256:' + 'a' * 64)


@pytest.mark.parametrize('target,expected', [
    ('sha256:' + 'a' * 64, True),
    ('registry.example:5000/team/app:1.2', True),
    ('sha256:' + 'b' * 64, True),
    ('<none>:<none>', False),
    ('app:missing', False),
])
def test_exists_uses_successful_inventory_for_ids_and_tags(harness, monkeypatch, target, expected):
    import json
    rows = [
        {'ID': 'sha256:' + 'a' * 64, 'Repository': 'registry.example:5000/team/app', 'Tag': '1.2'},
        {'ID': 'sha256:' + 'b' * 64, 'Repository': '<none>', 'Tag': '<none>'},
    ]

    def inventory(args, **kwargs):
        assert kwargs['check'] is True
        assert args[3:] == ['image', 'ls', '--all', '--no-trunc', '--format', '{{json .}}']
        return subprocess.CompletedProcess(args, 0, stdout='\n'.join(map(json.dumps, rows)))

    monkeypatch.setattr(subprocess, 'run', inventory)
    assert harness.exists(target) is expected


def test_host_management_ignores_inherited_remote_context(harness, monkeypatch):
    for key in ['DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH']:
        monkeypatch.setenv(key, 'inherited-remote-setting')

    def management(args, **kwargs):
        assert args == ['docker', '--host', 'unix:///var/run/docker.sock',
                        'exec', harness.CONTAINER_NAME, 'chmod', '666', '/qa-socket/docker.sock']
        assert not any(key in kwargs['env'] for key in [
            'DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH'])
        assert kwargs['check'] is True
        return subprocess.CompletedProcess(args, 0, stdout='')

    monkeypatch.setattr(subprocess, 'run', management)
    harness.host_docker('exec', harness.CONTAINER_NAME, 'chmod', '666', '/qa-socket/docker.sock')

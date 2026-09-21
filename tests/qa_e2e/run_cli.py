"""Real CLI + isolated Docker acceptance. Run explicitly with uv run python."""
import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys

from engine import QA_ROOT, SOCKET, containers, docker, guard, image

ROOT = Path(__file__).resolve().parents[2]
ENV = {**os.environ, 'DOCKER_HOST': f'unix://{SOCKET}'}
ENV.pop('DOCKER_CONTEXT', None)
REPORT = []


def config(name, keep=None, remove=False, force=False):
    path = QA_ROOT / f'{name}.yaml'
    path.write_text(json.dumps({'keep': keep if keep is not None else ['^(?!qa-case-)'],
                               'cleanup': {'remove_tags': remove, 'force': force}}))
    return path


def cli(name, path, answer='DELETE\n', env=None):
    result = subprocess.run(['uv', 'run', 'docker-clean', 'clean', '--config', str(path)],
                            cwd=ROOT, env=env or ENV, input=answer,
                            text=True, capture_output=True, timeout=90)
    (QA_ROOT / f'{name}.log').write_text(result.stdout + result.stderr + f'\nEXIT={result.returncode}\n')
    return result


def exists(target):
    return docker('image', 'inspect', target, check=False).returncode == 0


def record(name, function):
    try:
        function()
        REPORT.append({'case': name, 'status': 'PASS'})
    except Exception as exc:
        REPORT.append({'case': name, 'status': 'FAIL', 'detail': str(exc)})
    print(REPORT[-1], flush=True)
    (QA_ROOT / (Path(sys.argv[0]).stem + '-results.json')).write_text(json.dumps(REPORT, indent=2))


def matrix(remove, force):
    stem = f'qa-case-{int(remove)}{int(force)}'
    single = image(stem + '-single:latest')
    multi = image(stem + '-multi:a', stem + '-multi:b')
    protected = image(stem + '-protected:a', stem + '-protected:b')
    dangling = image(stem + '-overwrite:latest')
    image(stem + '-overwrite:latest')
    running = image(stem + '-running:latest')
    stopped = image(stem + '-stopped:latest')
    docker('run', '-d', '--name', stem + '-running', stem + '-running:latest', 'sleep', '36000')
    docker('run', '--name', stem + '-stopped', stem + '-stopped:latest', 'true')
    before = containers()
    path = config(stem, ['^(?!qa-case-)', '^' + stem + '-protected:a$'], remove, force)
    result = cli(stem, path)
    after = containers()
    (QA_ROOT / f'{stem}-container-equality.json').write_text(json.dumps({
        'before_sha256': hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest(),
        'after_sha256': hashlib.sha256(json.dumps(after, sort_keys=True).encode()).hexdigest(),
        'container_ids': [item['Id'] for item in before],
        'equal': before == after,
    }, indent=2))
    assert before == after, 'Full container inspect changed'
    assert exists(protected) and exists(stem + '-protected:a') and exists(stem + '-protected:b')
    assert not exists(single), 'single-tag image remains'
    assert not exists(dangling), 'untagged image remains'
    assert exists('busybox:1.37'), 'nonpreviewed parent deleted'
    assert exists(multi) == (not remove and not force), 'multi-tag outcome incorrect'
    assert stem + '-running (running' in result.stdout and stem + '-stopped (exited' in result.stdout
    if not force:
        assert exists(running) and exists(stopped), 'referenced image deleted without force'
    if not remove and not force:
        assert result.returncode != 0 and '失敗' in result.stdout
    assert 'Untagged:' in result.stdout and 'Deleted:' in result.stdout
    assert '共用層不可加總' in result.stdout
    # Remove only scenario fixtures inside the disposable daemon.
    docker('rm', '-f', stem + '-running', stem + '-stopped')
    for ident in {single, multi, protected, dangling, running, stopped}:
        docker('image', 'rm', '-f', '--no-prune', ident, check=False)


def invalid_configs():
    before = docker('image', 'ls', '-aq', '--no-trunc').stdout
    values = ['keep: [', 'keep: nope', 'keep: [1]', 'keep: ["["]',
              'keep: []\ncleanup: {force: "false"}', 'keep: []\ncleanup: {remove_tags: 1}']
    for i, value in enumerate(values):
        path = QA_ROOT / f'invalid-{i}.yaml'; path.write_text(value)
        result = cli(f'invalid-{i}', path)
        assert result.returncode != 0 and '停止' in result.stdout
    result = cli('missing', QA_ROOT / 'does-not-exist.yaml')
    assert result.returncode != 0
    path = QA_ROOT / 'unreadable.yaml'; path.write_text('keep: []'); path.chmod(0)
    try:
        assert cli('unreadable', path).returncode != 0
    finally:
        path.chmod(0o600)
    assert before == docker('image', 'ls', '-aq', '--no-trunc').stdout


def cancel_and_empty():
    before = docker('image', 'ls', '-aq', '--no-trunc').stdout
    result = cli('cancel', config('cancel', []), 'no\n')
    assert result.returncode == 0 and '已取消' in result.stdout and '沒有保留規則' in result.stdout
    assert before == docker('image', 'ls', '-aq', '--no-trunc').stdout
    result = cli('zero', config('zero', ['.']))
    assert result.returncode == 0 and '沒有清理候選' in result.stdout


def connection_errors():
    path = config('errors', [])
    for name, host in [('remote', 'tcp://127.0.0.1:2375'), ('ssh', 'ssh://example.invalid'),
                       ('absent-socket', f'unix://{QA_ROOT}/absent.sock')]:
        result = cli(name, path, env={**ENV, 'DOCKER_HOST': host})
        assert result.returncode != 0 and '停止' in result.stdout
        if name != 'absent-socket':
            assert '拒絕遠端' in result.stdout
    subprocess.run(['docker', 'exec', 'docker-clean-qa-toga-20260921', 'chmod', '000', '/qa-socket/docker.sock'], check=True)
    try:
        result = cli('permission', path)
        assert result.returncode != 0 and 'permission denied' in result.stdout.lower()
    finally:
        subprocess.run(['docker', 'exec', 'docker-clean-qa-toga-20260921', 'chmod', '666', '/qa-socket/docker.sock'], check=True)


if __name__ == '__main__':
    guard()
    docker('volume', 'create', 'qa-preserved-volume')
    if docker('network', 'inspect', 'qa-preserved-network', check=False).returncode:
        docker('network', 'create', 'qa-preserved-network')
    nonimage = {kind: docker(kind, 'inspect', 'qa-preserved-' + kind).stdout for kind in ['volume', 'network']}
    record('A04-invalid-configs', invalid_configs)
    for remove in [False, True]:
        for force in [False, True]:
            record(f'A03-A05-A06-A09-A10-A11-mode-{remove}-{force}', lambda r=remove, f=force: matrix(r, f))
    record('A07-cancel-zero-empty', cancel_and_empty)
    record('A09-A12-connections', connection_errors)
    record('A11-nonimage', lambda: all(nonimage[k] == docker(k, 'inspect', 'qa-preserved-' + k).stdout for k in nonimage) or (_ for _ in ()).throw(AssertionError('nonimage modified')))
    sys.exit(any(row['status'] == 'FAIL' for row in REPORT))

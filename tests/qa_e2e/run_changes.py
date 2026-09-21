"""Pause real CLI at its confirmation prompt, mutate isolated Engine, then confirm."""
import json
import os
import select
import subprocess
import time
from engine import QA_ROOT, docker, guard, image
from run_cli import REPORT, ENV, ROOT, config, exists, record


def changed(kind):
    tag = f'qa-case-change-{kind}:latest'
    original = image(tag)
    path = config('change-' + kind)
    process = subprocess.Popen(['uv', 'run', 'docker-clean', 'clean', '--config', str(path)],
                               cwd=ROOT, env=ENV, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    output = b''
    deadline = time.monotonic() + 30
    while b'DELETE' not in output and time.monotonic() < deadline:
        if select.select([process.stdout], [], [], 1)[0]:
            output += os.read(process.stdout.fileno(), 65536)
    assert b'DELETE' in output, 'No actual confirmation prompt'
    replacement = None
    if kind == 'config':
        path.write_text('keep: ["."]\n')
    elif kind == 'retarget':
        replacement = image('qa-replacement:latest')
        docker('tag', replacement, tag)
    elif kind == 'protected':
        docker('tag', original, 'protected-new:latest')
    elif kind == 'reference':
        docker('create', '--name', 'qa-new-reference', tag, 'true')
    rest, _ = process.communicate(b'DELETE\n', timeout=60)
    output = (output + rest).decode()
    (QA_ROOT / f'change-{kind}.log').write_text(output + f'\nEXIT={process.returncode}\n')
    assert exists(original), 'Original changed image deleted'
    if replacement:
        assert exists(replacement) and exists(tag), 'Replacement target deleted'
    assert '已改變' in output or '已變更' in output, 'Change not explained'
    if kind == 'config':
        assert process.returncode != 0
    if kind == 'reference':
        docker('rm', 'qa-new-reference')
    docker('image', 'rm', '-f', '--no-prune', original)


if __name__ == '__main__':
    guard()
    for kind in ['config', 'retarget', 'protected', 'reference']:
        record('A08-' + kind, lambda kind=kind: changed(kind))

    raise SystemExit(any(row["status"] == "FAIL" for row in REPORT))

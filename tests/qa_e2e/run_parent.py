"""Real Engine check for unpreviewed, untagged parent via public planning entry."""
import os
from engine import QA_ROOT, SOCKET, docker, guard, image
from run_cli import REPORT, config, exists, record
from docker_clean.config import load
from docker_clean.engine import Docker
from docker_clean.plan import execute, plan, render, render_results


def parent_retention():
    parent = image('qa-parent:latest')
    container = docker('create', 'qa-parent:latest', 'true').stdout.strip()
    child = docker('commit', '--change', 'LABEL qa.child=true', container, 'qa-child:latest').stdout.strip()
    docker('rm', container)
    # Repoint parent name to child, leaving a genuinely untagged parent.
    docker('tag', child, 'qa-parent:latest')
    assert docker('image', 'inspect', parent, '--format', '{{json .RepoTags}}').stdout.strip() == '[]'
    path = config('parent', [], force=True)
    value, revision = load(path)
    engine = Docker()
    snapshot = engine.snapshot()
    preview = plan(value, {child: snapshot[child]}, revision)
    results = execute(preview, path, engine)
    (QA_ROOT/'parent.log').write_text(render(preview)+'\n'+render_results(results))
    assert exists(parent), 'Unpreviewed parent was recursively removed'
    assert not exists(child), 'Child deletion did not execute'


if __name__ == '__main__':
    os.environ['DOCKER_HOST'] = f'unix://{SOCKET}'
    os.environ.pop('DOCKER_CONTEXT', None)
    guard()
    record('A11-unpreviewed-untagged-parent', parent_retention)

    raise SystemExit(any(row["status"] == "FAIL" for row in REPORT))

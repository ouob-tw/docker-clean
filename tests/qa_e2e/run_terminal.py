"""Real terminal acceptance: tmux keys/mouse -> installed TUI -> real Engine."""
import json
import shlex
import subprocess
import time
import uuid

import terminal as t
from engine import QA_ROOT, docker, guard, image
from run_cli import ENV, ROOT, exists


def select(identifier):
    ids = sorted(set(docker('image', 'ls', '-aq', '--no-trunc').stdout.split()))
    t.focus_table()
    t.keys(*(['Up'] * (len(ids) + 1)))
    t.keys(*(['Down'] * ids.index(identifier)))
    t.keys('Enter')


def replace_rules(value):
    t.click(8, 4)
    t.keys('F7')
    t.text(value)


def main():
    guard()
    t.SESSION = 'docker-clean-qa-replay'
    path = QA_ROOT / f'terminal-{uuid.uuid4().hex}.yaml'
    target = image('qa-ui-script:1.2', 'qa-ui-script:alias')
    command = shlex.join(['env', '-u', 'DOCKER_CONTEXT', f'DOCKER_HOST={ENV["DOCKER_HOST"]}',
                          'uv', 'run', 'docker-clean', 'tui', '--config', str(path)])
    subprocess.run(['tmux', 'new-session', '-d', '-s', t.SESSION, '-x', '200', '-y', '65',
                    '-c', str(ROOT), command], check=True)
    try:
        for _ in range(30):
            screen = t.capture('replay-start')
            if 'remove_tags=False, force=False' in screen:
                break
            time.sleep(0.2)
        assert 'remove_tags=False, force=False' in screen
        replace_rules('^qa-ui-script:1\\.2$')
        t.click_button('儲存')
        assert 'qa-ui-script' in path.read_text()
        t.capture('replay-exact-rule')
        replace_rules('^qa-ui-script:')
        t.keys('Enter'); t.text('^busybox:')
        t.click_button('儲存')
        assert 'busybox' in path.read_text()
        replace_rules('.')
        t.click_button('儲存')
        assert 'busybox' not in path.read_text()
        # Selection creates anchored, escaped exact tag rules.
        select(target)
        t.click_button('產生規則'); t.click_button('儲存')
        assert '^qa\\-ui\\-script:1\\.2$' in path.read_text()
        t.capture('replay-generated')
        # External save conflict must preserve external bytes.
        external = 'keep: ["."]\n'
        path.write_text(external)
        t.click_button('儲存')
        assert path.read_text() == external
        assert '外部修改' in t.capture('replay-external-conflict')
        t.click_button('重新載入')
        # Selected image disappears between user actions: exact original crash trigger.
        docker('image', 'rm', '--force', '--no-prune', target)
        t.click_button('預覽'); t.click_button('產生規則'); t.click_button('儲存')
        assert '已儲存' in t.capture('replay-stale-selection')
        # Preview -> cancel leaves full inventory unchanged.
        doomed = image('qa-ui-script-delete:latest')
        replace_rules('^(?!qa-ui-script-delete:)')
        t.click_button('儲存'); t.click_button('預覽')
        before = docker('image', 'ls', '-aq', '--no-trunc').stdout
        t.click_button('取消')
        assert '已取消' in t.capture('replay-cancel')
        assert before == docker('image', 'ls', '-aq', '--no-trunc').stdout
        # Preview -> confirm performs actual deletion and displays native outcomes.
        t.click_button('預覽')
        t.capture('replay-confirm-preview')
        t.click_button('確認刪除')
        for _ in range(30):
            screen = t.capture('replay-deleted')
            if '執行完畢' in screen:
                break
            time.sleep(0.2)
        assert not exists(doomed)
        assert 'Untagged:' in screen and 'Deleted:' in screen and '執行完畢' in screen
        (QA_ROOT/'run_terminal-results.json').write_text(json.dumps({
            'status': 'PASS', 'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
            'actions': ['default-options-off', 'add-edit-delete-rule', 'row-selection-generated-exact-regex',
                        'external-save-rejected', 'selected-disappearance-preview-generate',
                        'preview-cancel', 'preview-confirm-real-delete-visible-results'],
        }, indent=2))
        print('Real terminal acceptance PASS')
    finally:
        t.keys('C-q')


if __name__ == '__main__':
    main()

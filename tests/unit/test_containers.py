"""Policy and CLI tests use a fake Docker boundary, never host deletion."""
from datetime import datetime, timedelta, timezone
import json
import sys

import pytest
import yaml

from docker_clean import automation, containers
from docker_clean.config import CleanError, default_image_config


def item(identifier='a', status='exited', days=8, labels=None):
    return {'Id': identifier, 'Name': '/' + identifier,
            'State': {'Status': status, 'StartedAt': '2020-01-01T00:00:00Z',
                      'FinishedAt': (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()},
            'Config': {'Labels': labels or {}}, 'Mounts': []}


@pytest.fixture
def cli(tmp_path, monkeypatch, capsys):
    path = tmp_path / 'containers.yaml'
    policy = {'version': 1, 'stopped_days': 7, 'keep': {}}
    path.write_text(yaml.safe_dump(policy))

    class Fake:
        items = [item()]
        deleted = []
        inspections = 0
        change = None
        fail_rm = False

        def call(self, *args):
            if args[:2] == ('container', 'ls'):
                return '\n'.join(i['Id'] for i in self.items)
            if args[:2] == ('container', 'inspect'):
                self.inspections += 1
                if self.inspections > 1 and self.change:
                    self.change()
                return json.dumps([i for i in self.items if i['Id'] in args[2:]])
            assert args[:2] == ('container', 'rm') and len(args) == 3
            if self.fail_rm:
                raise CleanError('remove failure')
            self.deleted.append(args[2])
            return args[2]

    fake = Fake()
    monkeypatch.setattr(containers, 'Docker', lambda: fake)

    def run(execute=False, json_output=True, show_all=False):
        monkeypatch.setattr(sys, 'argv', ['dcl', 'container', 'clean', '--config', str(path),
                                       *(['--json'] if json_output else []), *(['--yes'] if execute else []),
                                       *(['--all'] if show_all else [])])
        code = automation.main()
        output = capsys.readouterr().out
        return code, json.loads(output) if json_output else output

    return fake, path, policy, run


def test_preview_and_execution(cli):
    fake, _, _, run = cli
    code, output = run()
    assert code == 0 and output['entries'][0]['delete'] and not fake.deleted
    assert output['empty_keep']
    code, output = run(True)
    assert code == 0 and fake.deleted == ['a'] and output['results'][0]['status'] == '刪除'


@pytest.mark.parametrize('status', ['running', 'paused', 'restarting', 'removing', 'created', 'dead'])
def test_non_exited_is_never_deleted(cli, status):
    fake, _, _, run = cli
    fake.items = [item(status=status)]
    assert run(True)[0] == 0 and not fake.deleted


def test_recently_stopped_old_container_kept(cli):
    fake, _, _, run = cli
    fake.items = [item(days=1)]
    assert run(True)[0] == 0 and not fake.deleted


@pytest.mark.parametrize('label', ['com.docker.swarm.task.id', 'com.docker.swarm.service.id'])
def test_swarm_skipped(cli, label):
    fake, _, _, run = cli
    fake.items = [item(labels={label: 'task'})]
    assert run(True)[0] == 0 and not fake.deleted


def test_exact_compose_scope_and_replicas(cli):
    fake, path, policy, run = cli
    policy['keep'] = {'compose': [{'project': 'full'}, {'project': 'app', 'services': ['db']}],
                      'container_names': ['manual']}
    path.write_text(yaml.safe_dump(policy))
    fake.items = [item('manual'), item('manual-other')]
    for identifier, project, service in [('a', 'full', 'web'), ('b', 'app', 'db'),
                                         ('c', 'app', 'db'), ('d', 'app', 'web'), ('e', 'other', 'db')]:
        fake.items.append(item(identifier, labels={'com.docker.compose.project': project,
                                                  'com.docker.compose.service': service}))
    assert run(True)[0] == 0
    assert fake.deleted == ['manual-other', 'd', 'e']


@pytest.mark.parametrize('edit', [
    {'stopped_days': True}, {'stopped_days': 0}, {'stopped_days': '7'}, {'version': True},
    {'keep': None}, {'keep': {'compose': [{'project': 'a', 'services': []}]}},
    {'keep': {'compose': [{'project': 'a', 'services': 'db'}]}},
    {'keep': {'containers': []}}, {'unknown': 1},
])
def test_bad_policy_fails_before_docker(cli, edit):
    fake, path, policy, run = cli
    policy.update(edit)
    path.write_text(yaml.safe_dump(policy))
    code, payload = run(True)
    assert code == 1 and payload['error'] and fake.inspections == 0 and not fake.deleted


@pytest.mark.parametrize('stamp', ['0001-01-01T00:00:00Z', 'invalid', '2099-01-01T00:00:00Z', '2020-01-01'])
def test_bad_finished_time_aborts_entire_plan(cli, stamp):
    fake, _, _, run = cli
    bad = item('b'); bad['State']['FinishedAt'] = stamp
    fake.items = [item(), bad]
    assert run(True)[0] == 1 and not fake.deleted


@pytest.mark.parametrize('change', ['restart', 'rename', 'labels', 'missing'])
def test_recheck_prevents_changed_container_removal(cli, change):
    fake, _, _, run = cli
    def mutate():
        if change == 'restart':
            fake.items[0]['State']['StartedAt'] = '2026-01-01T00:00:00Z'
        elif change == 'rename':
            fake.items[0]['Name'] = '/new'
        elif change == 'labels':
            fake.items[0]['Config']['Labels'] = {'new': 'label'}
        else:
            fake.items = []
    fake.change = mutate
    code, payload = run(True)
    assert code == (1 if change == 'missing' else 0) and not fake.deleted


def test_config_changes_stop_next_deletion_keep_receipts(cli):
    fake, path, _, run = cli
    fake.items = [item(), item('b')]
    fake.change = lambda: path.write_text('changed')
    code, payload = run(True)
    # Configuration is checked again after inspection, before any deletion.
    assert code == 1 and not fake.deleted


def test_rm_failure_reported(cli):
    fake, _, _, run = cli
    fake.fail_rm = True
    code, payload = run(True)
    assert code == 1 and payload['results'][0]['status'] == '失敗'


def test_default_image_path_ignores_old_filename(tmp_path, monkeypatch):
    monkeypatch.setattr('pathlib.Path.home', lambda: tmp_path)
    directory = tmp_path / '.config/docker-clean'; directory.mkdir(parents=True)
    assert default_image_config() == directory / 'images.yaml'
    (directory / 'config.yaml').write_text('keep: []')
    assert default_image_config() == directory / 'images.yaml'
    (directory / 'images.yaml').write_text('keep: []')
    assert default_image_config() == directory / 'images.yaml'


def test_exact_seven_day_boundary():
    now = datetime(2026, 9, 22, tzinfo=timezone.utc)
    policy = containers.Policy(7, (), ())
    for seconds, expected in [(7 * 86400 - 1, False), (7 * 86400, True), (7 * 86400 + 1, True)]:
        c = containers.Container('id', 'name', 'exited', 'start',
                                 (now - timedelta(seconds=seconds)).isoformat(), {}, ())
        assert containers.reason(c, policy, now)[0] is expected


def test_query_failure_preserves_previous_delete_receipt(cli):
    fake, _, _, run = cli
    fake.items = [item(), item('b')]
    def fail_later():
        if fake.inspections == 3:
            raise CleanError('inspect failure')
    fake.change = fail_later
    code, payload = run(True)
    assert code == 1 and fake.deleted == ['a']
    assert payload['results'][0]['id'] == 'a' and payload['error'] == 'inspect failure'


def test_missing_config_does_not_connect(cli):
    fake, path, _, run = cli
    path.rename(path.with_suffix('.backup'))
    assert run(True)[0] == 1 and fake.inspections == 0 and not fake.deleted


def test_text_default_candidates_and_all_only_affects_display(cli):
    fake, _, _, run = cli
    old = item('old')
    old['Mounts'] = [{'Type': 'bind', 'Source': '/old-data', 'Destination': '/data'}]
    kept = item('active', status='running')
    kept['Mounts'] = [{'Type': 'bind', 'Source': '/active-data', 'Destination': '/data'}]
    fake.items = [old, kept]
    code, text = run(json_output=False)
    assert code == 0 and 'old |' in text and '/old-data' in text
    assert 'active |' not in text and '/active-data' not in text
    assert '合計 2' in text and '刪除容器及內部檔案，保留掛載資料。' in text
    code, text = run(json_output=False, show_all=True)
    assert 'active |' in text and '/active-data' not in text
    assert not fake.deleted


def test_json_all_does_not_filter_report(cli):
    fake, _, _, run = cli
    fake.items = [item(), item('running', status='running'), item('recent', days=1)]
    _, normal = run()
    _, all_output = run(show_all=True)
    assert normal == all_output
    assert normal['summary'] == {'total': 3, 'candidate': 1, 'keep': 0,
                                 'too_recent': 1, 'swarm': 0, 'state': 1}
    assert normal['plan_complete'] and normal['stopped_days'] == 7


def test_zero_candidates_has_no_delete_hint(cli):
    fake, _, _, run = cli
    fake.items = [item(days=1)]
    code, text = run(json_output=False)
    assert code == 0 and '沒有刪除候選' in text
    assert '加上 --yes' not in text and '刪除容器及內部檔案' not in text


def test_incomplete_plan_never_reports_zero_candidates_as_success(cli):
    fake, _, _, run = cli
    fake.items[0]['State']['FinishedAt'] = 'invalid'
    code, text = run(execute=True, json_output=False)
    assert code == 1 and '盤點未完成' in text and '未處理 未知' in text
    assert '沒有刪除候選' not in text and not fake.deleted
    assert '--all' not in text and '刪除候選 0' not in text


def test_partial_execution_summary(cli):
    fake, _, _, run = cli
    fake.items = [item(), item('b')]
    def fail_later():
        if fake.inspections == 3:
            raise CleanError('inspect failure')
    fake.change = fail_later
    code, text = run(execute=True, json_output=False)
    assert code == 1 and '刪除 1 | 跳過 0 | 失敗 0 | 未處理 1' in text
    assert '停止：inspect failure' in text


def test_all_does_not_expand_execution_scope(cli):
    fake, _, _, run = cli
    fake.items = [item(), item('running', status='running')]
    code, text = run(execute=True, json_output=False, show_all=True)
    assert code == 0 and fake.deleted == ['a']
    assert '刪除 1 | 跳過 0 | 失敗 0 | 未處理 0' in text

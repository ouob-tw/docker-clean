"""Read real CLI preview to verify matching semantics; never confirm deletion."""
from engine import QA_ROOT, guard, image
from run_cli import REPORT, cli, config, record


def matching():
    tags = ['qa-case-match:1.2', 'qa-case-match:1x2', 'qa-case-match:1.20',
            'registry.example:5000/team/qa-case-match:1.2', 'other/qa-case-match:1.2']
    ids = {tag: image(tag) for tag in tags}
    cases = [
        (['^qa-case-match:1\\.2$'], {tags[0]}),
        (['^qa-case-match:'], set(tags[:3])),
        (['^registry\\.example:5000/team/qa-case-match:1\\.2$'], {tags[3]}),
        (['^qa-case-match:1\\.2$', '^other/'], {tags[0], tags[4]}),
        (['qa-case-match'], set(tags)),
    ]
    for index, (rules, expected) in enumerate(cases):
        result = cli('matching-' + str(index), config('matching-' + str(index), rules), 'cancel\n')
        assert result.returncode == 0
        protected = {tag for tag, ident in ids.items() if '保留 | ' + ident in result.stdout}
        assert protected == expected, (rules, protected, expected)
    (QA_ROOT/'matching-expectations.txt').write_text(repr(cases))


if __name__ == '__main__':
    guard()
    record('A02-regex-semantics', matching)

    raise SystemExit(any(row["status"] == "FAIL" for row in REPORT))

"""Drive real tmux terminal input; no app hooks or Textual test pilot."""
import subprocess
import time
from rich.cells import cell_len
from engine import QA_ROOT

SESSION = 'docker-clean-qa-toga'


def keys(*values):
    subprocess.run(['tmux', 'send-keys', '-t', SESSION, *values], check=True)
    time.sleep(0.25)


def text(value):
    keys('-l', value)


def click(x, y):
    text(f'\x1b[<0;{x};{y}M\x1b[<0;{x};{y}m')


def click_button(label):
    lines = subprocess.check_output(['tmux', 'capture-pane', '-p', '-t', SESSION], text=True).splitlines()
    for row, line in enumerate(lines, 1):
        if label in line and (('重新載入' in line and '重新盤點' in line)
                              or ('產生規則' in line and '確認刪除' in line)):
            click(cell_len(line[:line.index(label)]) + 1, row)
            return
    raise AssertionError(f'Button not visible: {label}')


def focus_table():
    lines = subprocess.check_output(['tmux', 'capture-pane', '-p', '-t', SESSION], text=True).splitlines()
    for row, line in enumerate(lines, 1):
        if '選' in line and 'tag' in line and '建立日期' in line:
            click(3, row + 1)
            return
    raise AssertionError('Image table not visible')


def capture(name):
    output = subprocess.check_output(['tmux', 'capture-pane', '-p', '-t', SESSION], text=True)
    (QA_ROOT / f'tui-{name}.txt').write_text(output)
    return output

"""Drive real tmux terminal input; no app hooks or Textual test pilot."""
import subprocess
import time
from engine import QA_ROOT

SESSION = 'docker-clean-qa-toga'


def keys(*values):
    subprocess.run(['tmux', 'send-keys', '-t', SESSION, *values], check=True)
    time.sleep(0.25)


def text(value):
    keys('-l', value)


def click(x, y):
    text(f'\x1b[<0;{x};{y}M\x1b[<0;{x};{y}m')


def capture(name):
    output = subprocess.check_output(['tmux', 'capture-pane', '-p', '-t', SESSION], text=True)
    (QA_ROOT / f'tui-{name}.txt').write_text(output)
    return output

# Independent real-engine acceptance

These tests belong to QA. They target a disposable Docker Engine and exercise the installed CLI and terminal TUI. Never point a destructive scenario at `/var/run/docker.sock`.

Preparation for reruns (management calls are explicitly pinned after harness review):

```bash
QA_ROOT=/tmp/docker-clean-qa-toga-20260921
unset DOCKER_CONTEXT DOCKER_HOST DOCKER_TLS DOCKER_TLS_VERIFY DOCKER_CERT_PATH
mkdir -p "$QA_ROOT/socket"
docker --host unix:///var/run/docker.sock pull docker:28-dind
docker --host unix:///var/run/docker.sock run -d --name docker-clean-qa-toga-20260921 \
  --label docker-clean.qa=toga-20260921 --privileged \
  --tmpfs /var/lib/docker:rw,exec,size=2g \
  -v "$QA_ROOT/socket:/qa-socket" \
  -e DOCKER_TLS_CERTDIR= docker:28-dind \
  dockerd --host unix:///qa-socket/docker.sock --storage-driver=vfs
```

No host Docker socket is mounted and no ports are published. The unique socket directory is the only host mount. Root filesystem changes, daemon state and its fixtures belong exclusively to this container. The shared pulled base image is retained on the host. Save evidence before removing the one owned container with `docker --host unix:///var/run/docker.sock rm -f docker-clean-qa-toga-20260921`.

Scenario commands, tested revisions and outcomes are recorded in `docs/qa/results.md`. The tests use a real disposable Engine; `run_terminal.py` drives real tmux keystrokes/mouse input. No mocks or Textual test pilot are used.

The socket is made usable by the QA user inside an owner-only parent directory:

```bash
chmod 700 "$QA_ROOT"
docker --host unix:///var/run/docker.sock exec docker-clean-qa-toga-20260921 chmod 666 /qa-socket/docker.sock
docker --host "unix://$QA_ROOT/socket/docker.sock" pull busybox:1.37
uv run --no-project python tests/qa_e2e/engine.py
```

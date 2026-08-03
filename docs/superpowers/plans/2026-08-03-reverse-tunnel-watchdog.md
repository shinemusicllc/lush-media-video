# Reverse Tunnel Watchdog Implementation Plan

> **For agentic workers:** Execute test-first; each code change must be proven by a failing test before implementation.

**Goal:** Automatically clear only verified stale reverse SSH listeners on the VPS so GPU workers can reconnect without restarting ComfyUI.

**Architecture:** A root-owned systemd timer calls one small shell script every minute. The script probes the two fixed reverse URLs, keeps ephemeral per-port consecutive-failure state, and sends `TERM` only to a still-verified `sshd: deploy` child owning the unhealthy allowlisted port. Existing Windows supervisors detect the closed SSH connection and recreate their tunnel.

**Tech Stack:** Bash, curl, iproute2 `ss`, procps `ps`, util-linux `flock`, systemd, Python `unittest`.

## Global Constraints

- Only ports `18188` and `18288` may be managed.
- Never use `pkill`, never stop ComfyUI or Docker, and send only `TERM`.
- Require two consecutive failed probes plus one immediate recheck before acting.
- Windows worker runtime configuration and SSH keys remain unchanged.

---

### Task 1: Safety-tested watchdog script

**Files:**
- Create: `deploy/scripts/watch_reverse_tunnels.sh`
- Create: `tests/test_reverse_tunnel_watchdog.py`

- [ ] Write tests proving a healthy probe clears state, one failure does not kill, two failures terminate a verified `deploy` `sshd` PID, and an unsafe candidate is refused.
- [ ] Run `python -m unittest tests.test_reverse_tunnel_watchdog -v`; confirm RED because script is absent.
- [ ] Implement command injection points for tests and production defaults for `curl`, `ss`, `ps`, `kill`, `logger`, `flock`, and `/run` state.
- [ ] Re-run the focused suite; confirm GREEN.

### Task 2: Systemd integration

**Files:**
- Create: `deploy/systemd/lush-media-reverse-tunnel-watchdog.service`
- Create: `deploy/systemd/lush-media-reverse-tunnel-watchdog.timer`
- Modify: `deploy/scripts/install_helpers.sh`
- Modify: `tests/test_reverse_tunnel_watchdog.py`

- [ ] Write tests asserting the timer is persistent, runs every minute, and installer enables it.
- [ ] Run focused suite; confirm RED.
- [ ] Add service/timer and installer wiring; run focused suite GREEN.

### Task 3: Documentation, regression, deployment

**Files:**
- Modify: `docs/modules/deploy.md`
- Modify: `docs/modules/gpu-workers.md`
- Modify: `docs/CHANGELOG.md`

- [ ] Run focused suite, all Python tests, worker PowerShell suites, shell syntax checks, and `git diff --check`.
- [ ] Commit and push the implementation.
- [ ] Pull the clean commit on VPS, install helpers, enable timer, and verify both health URLs/container status.
- [ ] With both queues empty, perform a controlled GPU2 tunnel recovery: terminate only its verified VPS SSH child and confirm the timer/worker sequence restores `18288` without affecting `18188`.

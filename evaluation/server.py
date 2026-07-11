"""MiniWeb server lifecycle management for evaluation.

Unlike WebArena-Infinity (one server per app), MiniWeb runs a single Flask
server hosting all sites. This module starts/stops that server and waits
for readiness.
"""

import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

PROJECT_ROOT = str(
    __import__("pathlib").Path(__file__).resolve().parent.parent
)


def kill_port(port: int):
    """Kill any process listening on the given port."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=5,
        )
        for pid in result.stdout.strip().split():
            if pid:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                except (ValueError, ProcessLookupError, PermissionError):
                    pass
        if result.stdout.strip():
            time.sleep(0.5)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


def start_server(port: int) -> subprocess.Popen:
    """Start the MiniWeb Flask server on the given port.

    Server output goes to a log file, NOT a pipe: with PIPE and no reader,
    the request log fills the 64KB pipe buffer after a few hundred requests
    and the server blocks on write — every request then hangs.
    """
    kill_port(port)
    env = os.environ.copy()
    env["FLASK_RUN_PORT"] = str(port)
    log = open(os.path.join(str(PROJECT_ROOT), "evaluation", f"server_{port}.log"), "w")
    return subprocess.Popen(
        [sys.executable, "run.py"],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )


def wait_for_server(port: int, host: str = "localhost", timeout: int = 30,
                     site_id: str = None) -> bool:
    """Poll until the server responds with 200 (uses stdlib to avoid urllib3 conflicts).

    If site_id is provided, also hits the site's index page to pre-warm
    any lazy data loading (e.g., reservoir sampling large datasets).
    """
    url = f"http://{host}:{port}/"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = urllib.request.urlopen(url, timeout=2)
            if r.status == 200:
                # Portal is up — now pre-warm the site if specified
                if site_id:
                    site_url = f"http://{host}:{port}/sites/{site_id}/"
                    try:
                        urllib.request.urlopen(site_url, timeout=60)
                    except (urllib.error.URLError, OSError):
                        pass  # Site may take time to load, that's ok
                return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.5)
    return False


def stop_server(proc: subprocess.Popen):
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()

"""Run the local Next.js and FastAPI development servers together."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
API_HOST = "127.0.0.1"
API_PORT = 8000
WEB_HOST = "127.0.0.1"
WEB_PORT = 3000
WEB_PORT_LIMIT = 3010


def _is_port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((WEB_HOST, port))
        except OSError:
            return False
    return True


def find_available_web_port(
    start: int = WEB_PORT,
    limit: int = WEB_PORT_LIMIT,
    *,
    is_available: Callable[[int], bool] = _is_port_available,
) -> int:
    """Return the first free port in the bounded local development range."""

    for port in range(start, limit + 1):
        if is_available(port):
            return port
    raise RuntimeError(f"No available local web port in range {start}-{limit}")


def _next_command(web_port: int) -> list[str]:
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Node.js is required; could not find 'node' on PATH")

    next_bin = ROOT / "node_modules" / "next" / "dist" / "bin" / "next"
    if not next_bin.is_file():
        raise RuntimeError(f"Next.js is not installed at {next_bin}")

    return [node, str(next_bin), "dev", "--hostname", WEB_HOST, "--port", str(web_port)]


def _api_command() -> list[str]:
    if importlib.util.find_spec("uvicorn") is None:
        raise RuntimeError("Uvicorn is required; install requirements-dev.txt first")

    return [
        sys.executable,
        "-m",
        "uvicorn",
        "api.service:app",
        "--host",
        API_HOST,
        "--port",
        str(API_PORT),
    ]


def check_runtime() -> None:
    """Fail fast when the checked-in local runtime wiring is incomplete."""

    package_path = ROOT / "package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    dev_script = package.get("scripts", {}).get("dev", "")
    if "scripts/dev.py" not in dev_script.replace("\\", "/"):
        raise RuntimeError("package.json dev script must run scripts/dev.py")

    next_config = (ROOT / "next.config.ts").read_text(encoding="utf-8")
    required_config = (
        'process.env.NODE_ENV !== "development"',
        'source: "/api/:path*"',
        'destination: `${localApiOrigin}/api/:path*`',
    )
    missing = [text for text in required_config if text not in next_config]
    if missing:
        raise RuntimeError(f"next.config.ts is missing local development rewrite pieces: {missing}")

    _api_command()
    selected_port = find_available_web_port()
    _next_command(selected_port)
    simulated_fallback = find_available_web_port(
        start=WEB_PORT,
        limit=WEB_PORT + 1,
        is_available=lambda port: port != WEB_PORT,
    )
    if simulated_fallback != WEB_PORT + 1:
        raise RuntimeError("web port fallback check did not select the next port")
    print(
        f"Local runtime wiring is ready: FastAPI {API_HOST}:{API_PORT} -> "
        f"browser http://{WEB_HOST}:{selected_port} (preferred port {WEB_PORT})"
    )


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return

    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return


def run_servers() -> int:
    api_process: subprocess.Popen[bytes] | None = None
    web_process: subprocess.Popen[bytes] | None = None
    try:
        web_port = find_available_web_port()
        print(
            f"GamePulse development runtime: browser http://{WEB_HOST}:{web_port} "
            f"(preferred port {WEB_PORT})",
            flush=True,
        )
        api_process = subprocess.Popen(_api_command(), cwd=ROOT)
        web_process = subprocess.Popen(
            _next_command(web_port),
            cwd=ROOT,
            env={**os.environ, "NODE_ENV": "development"},
            start_new_session=os.name != "nt",
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
        processes = (api_process, web_process)
        while True:
            for process in processes:
                return_code = process.poll()
                if return_code is not None:
                    if return_code == 0:
                        return 0
                    print(f"Development server exited with status {return_code}", file=sys.stderr)
                    return return_code
            time.sleep(0.1)
    except KeyboardInterrupt:
        return 0
    finally:
        for process in (web_process, api_process):
            if process is not None:
                _stop_process(process)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate local runtime wiring without starting servers")
    args = parser.parse_args()

    if args.check:
        check_runtime()
        return 0

    return run_servers()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"dev runtime error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

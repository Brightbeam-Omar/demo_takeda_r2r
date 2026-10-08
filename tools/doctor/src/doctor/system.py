"""What the checks ask of the machine, behind one small class so the tests can answer for it."""

import json
import socket
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Reply:
    code: int  # HTTP status, or 0 when nothing answered
    body: str


class System:
    """The real thing: shell commands, sockets, HTTP and files, relative to the repository root."""

    def __init__(self, root: Path, env: dict[str, str]) -> None:
        self.root = root
        self.env = env

    def run(self, command: list[str], timeout: float = 20) -> tuple[int, str]:
        try:
            done = subprocess.run(
                command, cwd=self.root, capture_output=True, text=True, timeout=timeout, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return 127, str(error)
        return done.returncode, (done.stdout + done.stderr).strip()

    def get(self, url: str, headers: dict[str, str] | None = None, timeout: float = 30) -> Reply:
        request = urllib.request.Request(url, headers=headers or {})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return Reply(response.status, response.read().decode())
        except urllib.error.HTTPError as error:
            return Reply(error.code, error.read().decode(errors="replace"))
        except (urllib.error.URLError, OSError, TimeoutError):
            return Reply(0, "")

    def port_in_use(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.5)
            return probe.connect_ex(("127.0.0.1", port)) == 0

    def exists(self, relative: str) -> bool:
        return (self.root / relative).is_file()

    def text(self, relative: str) -> str:
        try:
            return (self.root / relative).read_text()
        except OSError:
            return ""

    def json_lines(self, text: str) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for line in text.splitlines():
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if isinstance(value, dict):
                rows.append(value)
        return rows

import asyncio
import subprocess
import signal
import sys
import os
import time
from typing import Dict, List
from collections import deque

class GameProcess:
    def __init__(self, game_id: str, port: int, module_path: str):
        self.game_id = game_id
        self.port = port
        self.module_path = module_path
        self.process: subprocess.Popen = None
        self.logs: deque = deque(maxlen=1000) # Keep last 1000 log lines
        self._reader_task = None

    async def start(self):
        if self.is_running():
            return False

        # Build command: uvicorn games.dummy_game:app --port 8001
        cmd = [sys.executable, "-m", "uvicorn", self.module_path, "--port", str(self.port), "--host", "0.0.0.0"]

        # Start subprocess and pipe stdout/stderr (Cross-platform)
        kwargs = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "bufsize": 1 # Line buffered
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["preexec_fn"] = os.setsid

        self.process = subprocess.Popen(cmd, **kwargs)

        # Start async log reader
        self._reader_task = asyncio.create_task(self._read_logs())
        return True

    async def _read_logs(self):
        loop = asyncio.get_running_loop()
        while self.process and self.process.poll() is None:
            # Read line asynchronously
            line = await loop.run_in_executor(None, self.process.stdout.readline)
            if line:
                self.logs.append(f"[{self.game_id}] {line.strip()}")
            else:
                break

        # Capture remaining logs after process ends
        if self.process and self.process.stdout:
            for line in self.process.stdout.readlines():
                if line:
                    self.logs.append(f"[{self.game_id}] {line.strip()}")

    async def stop(self):
        if not self.is_running():
            return False

        pid = self.process.pid
        if sys.platform == "win32":
            try:
                # Force kill process tree on Windows
                subprocess.call(["taskkill", "/F", "/T", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                self.process.kill()
        else:
            # Send SIGTERM to the process group on POSIX
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except ProcessLookupError:
                pass

        # Wait gracefully for up to 2 seconds
        try:
            loop = asyncio.get_running_loop()
            await asyncio.wait_for(loop.run_in_executor(None, self.process.wait), timeout=2.0)
        except asyncio.TimeoutError:
            if sys.platform != "win32":
                try:
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
                    self.process.wait()
                except ProcessLookupError:
                    pass

        if self._reader_task:
            self._reader_task.cancel()
        self.process = None
        return True

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

class ProcessManager:
    def __init__(self):
        self.processes: Dict[str, GameProcess] = {}

    def register_game(self, game_id: str, port: int, module_path: str):
        self.processes[game_id] = GameProcess(game_id, port, module_path)

    async def start_game(self, game_id: str):
        if game_id in self.processes:
            return await self.processes[game_id].start()
        return False

    async def stop_game(self, game_id: str):
        if game_id in self.processes:
            return await self.processes[game_id].stop()
        return False

    def get_status(self) -> dict:
        status = {}
        for game_id, p in self.processes.items():
            status[game_id] = {
                "port": p.port,
                "running": p.is_running(),
                "pid": p.process.pid if p.is_running() else None
            }
        return status

    def get_logs(self, limit: int = 100) -> List[str]:
        all_logs = []
        # Aggregate logs from all running processes
        for p in self.processes.values():
            all_logs.extend(list(p.logs))
        # Optional: sort logs if there were timestamps, but order of appends works roughly.
        return all_logs[-limit:]

# Singleton instance
manager = ProcessManager()

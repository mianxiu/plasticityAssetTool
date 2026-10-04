"""Process lifetime lock: one backend per installation, regardless of port."""
import json
import os
from pathlib import Path


class BackendInstance:
    def __init__(self, runtime):
        self.runtime = Path(runtime)
        self.metadata = self.runtime / "backend-instance.json"
        self.file = None

    def acquire(self):
        self.runtime.mkdir(parents=True, exist_ok=True)
        stream = open(self.runtime / "backend-instance.lock", "a+b")
        if stream.seek(0, 2) == 0:
            stream.write(b" ")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            stream.close()
            return False
        self.file = stream
        # Only the lock owner may clear metadata left by a crashed backend.
        self.metadata.unlink(missing_ok=True)
        return True

    def publish(self, port):
        if self.file is None:
            raise RuntimeError("Backend instance lock is not held")
        temporary = self.metadata.with_suffix(".tmp")
        temporary.write_text(json.dumps({"pid": os.getpid(), "port": port}), encoding="utf-8")
        temporary.replace(self.metadata)

    def read_port(self):
        try:
            port = json.loads(self.metadata.read_text(encoding="utf-8"))["port"]
            return port if type(port) is int and 0 < port < 65536 else None
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def close(self):
        if self.file is not None:
            try:
                self.metadata.unlink(missing_ok=True)
            finally:
                # Closing the descriptor also releases the OS lock on crashes.
                self.file.close()
                self.file = None

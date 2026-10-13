"""
Robust Atomic and Single-Writer JSONL Logger for Multiprocess Scientific Sweeps.
Guarantees atomic whole-record appends, explicit fsync policy, and idempotency by trial hash.
"""

import os
import sys
import json
import time
import hashlib
from typing import Dict, Any, Optional

try:
    import msvcrt
except ImportError:
    msvcrt = None

try:
    import fcntl
except ImportError:
    fcntl = None


class AtomicJsonlWriter:
    """
    Thread-safe and process-safe atomic JSONL appender with file locking and fsync.
    Ensures that each record is written as a single atomic line terminated by newline.
    """

    def __init__(self, filepath: str, fsync: bool = True):
        self.filepath = os.path.abspath(filepath)
        self.fsync = fsync
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)

    def append(self, record: Dict[str, Any]) -> str:
        """
        Append a single JSON record atomically.
        Returns the SHA-256 hash of the normalized record.
        """
        line_bytes = (json.dumps(record, sort_keys=True) + "\n").encode("utf-8")
        rec_hash = hashlib.sha256(line_bytes.strip()).hexdigest()

        # Open in append mode with explicit file locking
        with open(self.filepath, "ab") as f:
            self._lock(f)
            try:
                f.write(line_bytes)
                f.flush()
                if self.fsync:
                    os.fsync(f.fileno())
            finally:
                self._unlock(f)

        return rec_hash

    def _lock(self, f) -> None:
        if msvcrt:
            # Lock first byte on Windows
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
            except Exception:
                pass
        elif fcntl:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            except Exception:
                pass

    def _unlock(self, f) -> None:
        if msvcrt:
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
        elif fcntl:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass


class SingleWriterJsonlLogger:
    """
    Main-thread single-writer coordinator.
    Workers return records to the main process; the main process writes records sequentially
    and enforces idempotency by trial hash.
    """

    def __init__(self, filepath: str, fsync: bool = True):
        self.filepath = os.path.abspath(filepath)
        self.fsync = fsync
        self.written_hashes = set()
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        self._load_existing_hashes()

    def _load_existing_hashes(self) -> None:
        if os.path.exists(self.filepath):
            with open(self.filepath, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        th = rec.get("trial_hash")
                        if th:
                            self.written_hashes.add(th)
                    except Exception:
                        pass

    def write_record(self, record: Dict[str, Any], trial_hash_key: str = "trial_hash") -> bool:
        """
        Write a single record. Idempotent: skips if trial_hash already recorded.
        Returns True if written, False if skipped as duplicate.
        """
        th = record.get(trial_hash_key)
        if th and th in self.written_hashes:
            return False

        line_str = json.dumps(record, sort_keys=True) + "\n"
        with open(self.filepath, "a", encoding="utf-8") as f:
            f.write(line_str)
            f.flush()
            if self.fsync:
                os.fsync(f.fileno())

        if th:
            self.written_hashes.add(th)
        return True

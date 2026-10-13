"""
Robust Atomic and Single-Writer JSONL Logger for Multiprocess Scientific Sweeps.
Guarantees atomic whole-record appends, explicit fsync policy, per-record SHA-256 hashes,
cross-platform file locking (via filelock/msvcrt/fcntl), and idempotency by trial hash.
Fail-closed: lock acquisition failures raise LockAcquisitionError.
"""

import os
import sys
import json
import time
import hashlib
import threading
from typing import Dict, Any, Optional

try:
    from filelock import FileLock, Timeout as FileLockTimeout
except ImportError:
    FileLock = None
    FileLockTimeout = None

try:
    import msvcrt
except ImportError:
    msvcrt = None

try:
    import fcntl
except ImportError:
    fcntl = None


class LockAcquisitionError(RuntimeError):
    """Raised when process file lock cannot be acquired."""
    pass


def compute_record_hash(record: Dict[str, Any]) -> str:
    """
    Compute canonical SHA-256 digest of record content, excluding any existing record_sha256 field.
    Uses canonical JSON serialization: sort_keys=True, separators=(',', ':').
    """
    clean_record = {k: v for k, v in record.items() if k != "record_sha256"}
    canonical_bytes = json.dumps(clean_record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


_THREAD_LOCKS: Dict[str, threading.Lock] = {}
_META_LOCK = threading.Lock()


def _get_thread_lock(filepath: str) -> threading.Lock:
    with _META_LOCK:
        if filepath not in _THREAD_LOCKS:
            _THREAD_LOCKS[filepath] = threading.Lock()
        return _THREAD_LOCKS[filepath]


class AtomicJsonlWriter:
    """
    Thread-safe and process-safe atomic JSONL appender with cross-platform file locking and fsync.
    Ensures that each record is written as a single atomic line terminated by newline.
    Persists canonical per-record SHA-256 hash inside each record.
    Fails closed: raises LockAcquisitionError if lock cannot be acquired.
    """

    def __init__(self, filepath: str, fsync: bool = True, timeout: float = 10.0):
        self.filepath = os.path.abspath(filepath)
        self.fsync = fsync
        self.timeout = timeout
        self.lock_filepath = self.filepath + ".lock"
        self._tlock = _get_thread_lock(self.filepath)
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        if FileLock is not None:
            self._file_lock = FileLock(self.lock_filepath, timeout=self.timeout)
        else:
            self._file_lock = None

    def append(self, record: Dict[str, Any]) -> str:
        """
        Append a single JSON record atomically.
        Persists and returns the canonical SHA-256 hash of the record.
        """
        rec_copy = dict(record)
        rec_hash = compute_record_hash(rec_copy)
        rec_copy["record_sha256"] = rec_hash
        # Update caller's dictionary as well
        record["record_sha256"] = rec_hash

        line_bytes = (json.dumps(rec_copy, sort_keys=True) + "\n").encode("utf-8")

        with self._tlock:
            if self._file_lock is not None:
                try:
                    with self._file_lock:
                        with open(self.filepath, "a+b") as f:
                            f.seek(0, os.SEEK_END)
                            f.write(line_bytes)
                            f.flush()
                            if self.fsync:
                                os.fsync(f.fileno())
                except FileLockTimeout as e:
                    raise LockAcquisitionError(
                        f"Failed to acquire filelock on {self.lock_filepath} after {self.timeout}s: {e}"
                    ) from e
                except Exception as e:
                    if not isinstance(e, LockAcquisitionError):
                        raise LockAcquisitionError(f"Error acquiring filelock on {self.lock_filepath}: {e}") from e
                    raise
            else:
                # Fallback to msvcrt or fcntl with fail-closed semantics
                with open(self.filepath, "a+b") as f:
                    self._lock_or_raise(f)
                    try:
                        f.seek(0, os.SEEK_END)
                        f.write(line_bytes)
                        f.flush()
                        if self.fsync:
                            os.fsync(f.fileno())
                    finally:
                        self._unlock(f)

        return rec_hash

    def _lock_or_raise(self, f) -> None:
        if msvcrt:
            for attempt in range(100):
                try:
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                    return
                except (OSError, IOError):
                    time.sleep(0.002 * (1 + (attempt % 5)))
            try:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
                return
            except (OSError, IOError) as e:
                raise LockAcquisitionError(f"msvcrt lock failed on {self.filepath}: {e}") from e
        elif fcntl:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                return
            except Exception as e:
                raise LockAcquisitionError(f"fcntl lock failed on {self.filepath}: {e}") from e
        else:
            raise LockAcquisitionError(
                f"No locking backend available (filelock, msvcrt, and fcntl all unavailable) for {self.filepath}"
            )

    def _unlock(self, f) -> None:
        if msvcrt:
            try:
                f.seek(0)
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
    Persists canonical per-record SHA-256 hash.
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

        rec_copy = dict(record)
        rec_hash = compute_record_hash(rec_copy)
        rec_copy["record_sha256"] = rec_hash
        record["record_sha256"] = rec_hash

        line_str = json.dumps(rec_copy, sort_keys=True) + "\n"
        with open(self.filepath, "a", encoding="utf-8") as f:
            f.write(line_str)
            f.flush()
            if self.fsync:
                os.fsync(f.fileno())

        if th:
            self.written_hashes.add(th)
        return True

"""Serialize deposits and recover filesystem state after an interrupted write."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil


@contextmanager
def archive_lock(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".ripper.lock").open("a+b") as handle:
        if os.name == "nt":
            import msvcrt
            handle.write(b"0")
            handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def recover(root: Path) -> bool:
    """Call under archive_lock; repeated recovery is safe if interrupted."""
    transaction = root / ".ripper-transaction"
    journal = transaction / "journal.json"
    if not journal.exists():
        if transaction.exists():
            shutil.rmtree(transaction)
        return False
    state = json.loads(journal.read_text(encoding="utf-8"))
    name = state["target"]
    if not name or Path(name).name != name or name.startswith("."):
        raise ValueError("invalid transaction target")
    target = root / name
    if state["status"] == "pending":
        backup = transaction / "backup"
        if state["existed"] and not backup.is_dir():
            raise ValueError("interrupted deposit backup is missing; refusing recovery")
        if target.exists():
            shutil.rmtree(target)
        if state["existed"]:
            shutil.copytree(backup, target)
    elif state["status"] != "committed":
        raise ValueError("invalid transaction status")
    shutil.rmtree(transaction)
    return True


def write_journal(path: Path, state: dict):
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(state, handle)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


@contextmanager
def deposit_transaction(root: Path, target: Path):
    transaction = root / ".ripper-transaction"
    transaction.mkdir()
    existed = target.is_dir()
    if existed:
        shutil.copytree(target, transaction / "backup")
    journal = transaction / "journal.json"
    state = {"target": target.name, "existed": existed, "status": "pending"}
    write_journal(journal, state)
    try:
        yield
        state["status"] = "committed"
        write_journal(journal, state)
    except BaseException:
        recover(root)
        raise
    else:
        shutil.rmtree(transaction)

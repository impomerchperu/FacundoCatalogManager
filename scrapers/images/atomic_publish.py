from __future__ import annotations

import errno
import os
from pathlib import Path

_WINDOWS_LINK_ERRORS = {
    errno.EACCES,
    errno.EPERM,
    getattr(errno, "ENOTSUP", errno.EPERM),
    getattr(errno, "EOPNOTSUPP", errno.EPERM),
}


def publish_file_without_overwrite(temporary: Path, destination: Path) -> None:
    """Atomically publish a same-directory temp without replacing a file.

    Hard links provide no-replace semantics on POSIX and on ordinary NTFS
    volumes. Some Windows sandboxes and filesystems deny hard links; Windows
    ``os.rename`` is also atomic and fails if the destination already exists.
    """
    try:
        os.link(temporary, destination)
    except FileExistsError:
        raise
    except OSError as error:
        if os.name != "nt" or error.errno not in _WINDOWS_LINK_ERRORS:
            raise
        os.rename(temporary, destination)

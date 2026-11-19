"""Print the protocols mmt-dpi registers once it has loaded its plugins.

Run by ``mmt_plugin.sdk.registry`` in a child process (``python -I``), never
imported: loading plugins runs their native code, which may crash or print,
so the caller's process stays out of it. It imports nothing from
``mmt_plugin``. Arguments: the ``libmmt_core`` shared object and
``PROTO_MAX_IDENTIFIER``. The plugins are those of ``$MMT_DPI_PLUGINS_DIR``,
which the caller sets.

It loads ``libmmt_core`` (global symbols, so the plugins resolve against
it), calls ``init_extraction()``, then asks ``is_registered_protocol()`` and
``get_protocol_name_by_id()`` for every id below the maximum. The result is
one JSON object on the original stdout: ``{"ok": true, "protocols":
[[id, name], ...]}``, or ``{"ok": false, "error": "..."}``. Anything the
library prints goes to stderr, since stdout is moved there first.
"""

from __future__ import annotations

import ctypes
import json
import os
import sys


def main(argv: list[str]) -> None:
    out = os.fdopen(os.dup(1), "w", encoding="utf-8")
    os.dup2(2, 1)  # whatever mmt-dpi prints on stdout goes to stderr
    core, max_id = argv[1], int(argv[2])
    try:
        lib = ctypes.CDLL(core, mode=ctypes.RTLD_GLOBAL)
    except OSError as exc:
        report: dict[str, object] = {"ok": False, "error": f"cannot load {core}: {exc}"}
    else:
        lib.init_extraction.restype = ctypes.c_bool
        lib.init_extraction.argtypes = []
        lib.is_registered_protocol.restype = ctypes.c_bool
        lib.is_registered_protocol.argtypes = [ctypes.c_uint32]
        lib.get_protocol_name_by_id.restype = ctypes.c_char_p
        lib.get_protocol_name_by_id.argtypes = [ctypes.c_uint32]
        if not lib.init_extraction():
            report = {"ok": False, "error": "init_extraction() failed"}
        else:
            protocols: list[list[object]] = []
            for pid in range(max_id):
                if lib.is_registered_protocol(pid):
                    name = lib.get_protocol_name_by_id(pid)
                    text = "" if name is None else name.decode("utf-8", "replace")
                    protocols.append([pid, text])
            report = {"ok": True, "protocols": protocols}
    out.write(json.dumps(report) + "\n")
    out.flush()
    # No close_extraction() and no interpreter teardown: a plugin's
    # destructors cannot change the answer, only crash after it.
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv)

#!/usr/bin/env python3
import subprocess
import dataclasses
from typing import Any

import pwncat
from pwncat.platform.linux import Linux
from pwncat import util
from pwncat.modules import Status
from pwncat.modules.agnostic.enumerate import EnumerateModule, Schedule
from pwncat.modules.linux.enumerate.ability import (
    GTFOFileRead,
    GTFOFileWrite,
    GTFOExecute,
)
from pwncat.gtfobins import Capability, Stream, BinaryNotFound
from pwncat.db import Fact


class Binary(Fact):
    """
    A generic description of a SUID binary
    """

    def __init__(self, source, path, uid):
        super().__init__(source=source, types=["file.suid"])

        """ The path to the binary """
        self.path: str = path

        """ The uid of the binary """
        self.uid: int = uid

    def __str__(self):
        color = "red" if self.uid == 0 else "green"
        return f"[cyan]{self.path}[/cyan] owned by [{color}]{self.uid}[/{color}]"


class Module(EnumerateModule):
    """Enumerate SUID binaries on the remote host"""

    PROVIDES = [
        "file.suid",
        "ability.execute",
        "ability.file.read",
        "ability.file.write",
    ]
    PLATFORM = [Linux]
    SCHEDULE = Schedule.PER_USER

    def enumerate(self, session: "pwncat.manager.Session"):

        # Spawn a find command to locate the setuid binaries
        proc = session.platform.Popen(
            ["find", "/", "-perm", "-4000", "-printf", "%U %p\\n"],
            stderr=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            text=True,
        )

        facts = []
        with proc.stdout as stream:
            for path in stream:
                # Parse out owner ID and path
                path = path.strip().split(" ")
                uid, path = int(path[0]), " ".join(path[1:])

                fact = Binary(self.name, path, uid)
                yield fact

                for method in session.platform.gtfo.iter_binary(path):
                    if method.cap == Capability.READ:
                        yield GTFOFileRead(
                            source=self.name,
                            uid=uid,
                            method=method,
                            suid=True,
                        )
                    if method.cap == Capability.WRITE:
                        yield GTFOFileWrite(
                            source=self.name,
                            uid=uid,
                            method=method,
                            suid=True,
                            length=100000000000,  # TO-DO: WE SHOULD FIX THIS???
                        )
                    if method.cap == Capability.SHELL:
                        yield GTFOExecute(
                            source=self.name,
                            uid=uid,
                            method=method,
                            suid=True,
                        )

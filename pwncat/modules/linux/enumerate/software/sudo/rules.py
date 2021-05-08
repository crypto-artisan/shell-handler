#!/usr/bin/env python3
import dataclasses
import re
from typing import Generator, Optional, List

import rich.markup

import pwncat
from pwncat import util
from pwncat.db import Fact
from pwncat.platform.linux import Linux
from pwncat.modules.agnostic.enumerate import EnumerateModule, Schedule


"""
TODO: This should end up yielding an escalation ability, since sudo 
will... inherently give us the potential to run things as the root user.
We can implement that later after all the enumeration modules are set.
"""

per_user = True
sudo_pattern = re.compile(
    r"""(%?[a-zA-Z][a-zA-Z0-9_]*)\s+([a-zA-Z_][-a-zA-Z0-9_.]*)\s*="""
    r"""(\([a-zA-Z_][-a-zA-Z0-9_]*(:[a-zA-Z_][a-zA-Z0-9_]*)?(,\ *!?[a-zA-Z_][-a-zA-Z0-9_]*(:[a-zA-Z_][a-zA-Z0-9_]*)?)*\)|[a-zA-Z_]"""
    r"""[a-zA-Z0-9_]*)?\s+((NOPASSWD:\s+)|(SETENV:\s+)|(sha[0-9]{1,3}:"""
    r"""[-a-zA-Z0-9_]+\s+))*(.*)"""
)

directives = ["Defaults", "User_Alias", "Runas_Alias", "Host_Alias", "Cmnd_Alias"]


class SudoSpec(Fact):
    def __init__(
        self,
        source,
        line: str,
        matched: bool = False,
        user: Optional[str] = None,
        group: Optional[str] = None,
        host: Optional[str] = None,
        runas_user: Optional[str] = None,
        runas_group: Optional[str] = None,
        options: List[str] = None,
        hash: str = None,
        commands: List[str] = None,
    ):
        super().__init__(source=source, types=["software.sudo.rule"])

        self.line: str = line
        """ The full, unaltered line from the sudoers file """
        self.matched: bool = False
        """ The regular expression match data. If this is None, all following fields
        are invalid and should not be used. """
        self.user: Optional[str] = None
        """ The user which this rule applies to. This is None if a group was specified """
        self.group: Optional[str] = None
        """ The group this rule applies to. This is None if a user was specified. """
        self.host: Optional[str] = None
        """ The host this rule applies to """
        self.runas_user: Optional[str] = None
        """ The user we are allowed to run as """
        self.runas_group: Optional[str] = None
        """ The GID we are allowed to run as (may be None)"""
        self.options: List[str] = None
        """ A list of options specified (e.g. NOPASSWD, SETENV, etc) """
        self.hash: str = None
        """ A hash type and value which sudo will obey """
        self.commands: List[str] = None
        """ The command specification """

    def title(self, session):
        display = ""

        if not self.matched:
            return self.line

        if self.user is not None:
            display += f"User [blue]{rich.markup.escape(self.user)}[/blue]: "
        else:
            display += f"Group [cyan]{rich.markup.escape(self.group)}[/cyan]: "

        display += f"[yellow]{'[/yellow], [yellow]'.join((rich.markup.escape(x) for c in self.commands))}[/yellow] as "

        if self.runas_user == "root":
            display += f"[red]root[/red]"
        elif self.runas_user is not None:
            display += f"[blue]{rich.markup.escape(self.runas_user)}[/blue]"

        if self.runas_group == "root":
            display += f":[red]root[/red]"
        elif self.runas_group is not None:
            display += f"[cyan]{rich.markup.escape(self.runas_group)}[/cyan]"

        if self.host is not None:
            display += f" on [magenta]{rich.markup.escape(self.host)}[/magenta]"

        if self.options:
            display += (
                " ("
                + ",".join(
                    f"[green]{rich.markup.escape(x)}[/green]" for x in self.options
                )
                + ")"
            )

        return display

    def description(self, session):
        return None


def LineParser(source, line):
    match = sudo_pattern.search(line)

    if match is None:
        return SudoSpec(source, line, matched=False, options=[])

    user = match.group(1)

    if user in directives:
        return SudoSpec(source, line, matched=False, options=[])

    if user.startswith("%"):
        group = user.lstrip("%")
        user = None
    else:
        group = None

    host = match.group(2)

    if match.group(3) is not None:
        runas_user = match.group(3).lstrip("(").rstrip(")")
        if match.group(4) is not None:
            runas_group = match.group(4).lstrip(" ")
            runas_user = runas_user.split(":")[0].rstrip(" ")
        else:
            runas_group = None
        if runas_user == "":
            runas_user = "root"
    else:
        runas_user = "root"
        runas_group = None

    options = []
    hash = None

    for g in map(match.group, [8, 9, 10]):
        if g is None:
            continue

        options.append(g.strip().rstrip(":"))
        if g.startswith("sha"):
            hash = g

    command = match.group(11)
    commands = re.split(r"""(?<!\\), ?""", command)

    return SudoSpec(
        source,
        line,
        True,
        user,
        group,
        host,
        runas_user,
        runas_group,
        options,
        hash,
        commands,
    )


class Module(EnumerateModule):
    """Enumerate sudo privileges for the current user. If allowed,
    this module will also enumerate sudo rules for other users. Normally,
    root permissions are needed to read /etc/sudoers."""

    PROVIDES = ["software.sudo.rule"]
    PLATFORM = [Linux]
    SCHEDULE = Schedule.PER_USER

    def enumerate(self, session):

        try:
            etc_sudoers = session.platform.Path("/etc/sudoers")
            if etc_sudoers.readable():
                with etc_sudoers.open() as filp:
                    for line in filp:
                        line = line.strip()
                        # Ignore comments and empty lines
                        if line.startswith("#") or line == "":
                            continue

                        yield LineParser(self.name, line)

                # No need to parse `sudo -l`, since can read /etc/sudoers
                return
        except (FileNotFoundError, PermissionError):
            pass

        # Check for our privileges
        try:

            proc = session.platform.sudo(["sudo", "-nl"], as_is=True, text=True)
            result = proc.stdout.read()
            proc.wait()  # ensure this closes properly

        except PermissionError:
            # if this asks for a password and we don't have one, bail
            return

        for line in result.split("\n"):
            line = line.rstrip()

            # Skipe header lines
            if not line.startswith(" ") and not line.startswith("\t"):
                continue

            # Strip beginning whitespace
            line = line.strip()

            # Skip things that aren't user specifications
            if not line.startswith("("):
                continue

            # Build the beginning part of a normal spec
            line = f"{session.current_user().name} local=" + line.strip()
            yield LineParser(self.name, line)

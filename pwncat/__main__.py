#!/usr/bin/env python3
import os
import sys
import shlex
import logging
import argparse
import warnings
import selectors
from io import TextIOWrapper
from pathlib import Path

from rich import box
from rich.table import Table
from sqlalchemy import exc as sa_exc
from rich.progress import Progress
from sqlalchemy.exc import InvalidRequestError
from paramiko.buffered_pipe import BufferedPipe

import pwncat.manager
from pwncat.util import console
from pwncat.commands import connect


def main():

    # Ignore SQL Alchemy warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=sa_exc.SAWarning)

        # Default log-level is "INFO"
        logging.getLogger().setLevel(logging.INFO)

        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--config",
            "-c",
            type=argparse.FileType("r"),
            default=None,
            help="Custom configuration file (default: ./pwncatrc)",
        )
        parser.add_argument(
            "--identity",
            "-i",
            type=argparse.FileType("r"),
            default=None,
            help="Private key for SSH authentication",
        )
        parser.add_argument(
            "--listen",
            "-l",
            action="store_true",
            help="Enable the `bind` protocol (supports netcat-style syntax)",
        )
        parser.add_argument(
            "--platform", "-m", help="Name of the platform to use (default: linux)"
        )
        parser.add_argument(
            "--port",
            "-p",
            help="Alternative way to specify port to support netcat-style syntax",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="List installed implants with remote connection capability",
        )
        parser.add_argument(
            "connection_string",
            metavar="[protocol://][user[:password]@][host][:port]",
            help="Connection string describing victim",
            nargs="?",
        )
        parser.add_argument(
            "pos_port",
            nargs="?",
            metavar="port",
            help="Alternative port number to support netcat-style syntax",
        )
        args = parser.parse_args()

        # Create the session manager
        with pwncat.manager.Manager(args.config) as manager:

            if args.list:

                db = manager.db.open()
                implants = []

                table = Table(
                    "ID",
                    "Address",
                    "Platform",
                    "Implant",
                    "User",
                    box=box.MINIMAL_DOUBLE_HEAD,
                )

                # Locate all installed implants
                for target in db.root.targets:

                    # Collect users
                    users = {}
                    for fact in target.facts:
                        if "user" in fact.types:
                            users[fact.id] = fact

                    # Collect implants
                    for fact in target.facts:
                        if "implant.remote" in fact.types:
                            table.add_row(
                                target.guid,
                                target.public_address[0],
                                target.platform,
                                fact.source,
                                users[fact.uid].name,
                            )

                console.print(table)

                return

            if (
                args.connection_string is not None
                or args.pos_port is not None
                or args.port is not None
                or args.platform is not None
                or args.listen is not None
                or args.identity is not None
            ):
                protocol = None
                user = None
                password = None
                host = None
                port = None
                try_reconnect = False

                if args.connection_string:
                    m = connect.Command.CONNECTION_PATTERN.match(args.connection_string)
                    protocol = m.group("protocol")
                    user = m.group("user")
                    password = m.group("password")
                    host = m.group("host")
                    port = m.group("port")

                if protocol is not None and args.listen:
                    console.log(
                        f"[red]error[/red]: --listen is not compatible with an explicit connection string"
                    )
                    return

                if (
                    sum(
                        [
                            port is not None,
                            args.port is not None,
                            args.pos_port is not None,
                        ]
                    )
                    > 1
                ):
                    console.log(f"[red]error[/red]: multiple ports specified")
                    return

                if args.port is not None:
                    port = args.port
                if args.pos_port is not None:
                    port = args.pos_port

                if port is not None:
                    try:
                        port = int(port.lstrip(":"))
                    except:
                        console.log(f"[red]error[/red]: {port}: invalid port number")
                        return

                if protocol != "ssh://" and args.identity is not None:
                    console.log(
                        f"[red]error[/red]: --identity is only valid for ssh protocols"
                    )
                    return

                # Attempt to reconnect via installed implants
                if (
                    protocol is None
                    and password is None
                    and port is None
                    and args.identity is None
                ):
                    db = manager.db.open()
                    implants = []

                    # Locate all installed implants
                    for target in db.root.targets:

                        if target.guid != host and target.public_address[0] != host:
                            continue

                        # Collect users
                        users = {}
                        for fact in target.facts:
                            if "user" in fact.types:
                                users[fact.id] = fact

                        # Collect implants
                        for fact in target.facts:
                            if "implant.remote" in fact.types:
                                implants.append((target, users[fact.uid], fact))

                    with Progress(
                        "triggering implant",
                        "•",
                        "{task.fields[status]}",
                        transient=True,
                        console=console,
                    ) as progress:
                        task = progress.add_task("", status="...")
                        for target, implant_user, implant in implants:
                            # Check correct user
                            if user is not None and implant_user.name != user:
                                continue
                            # Check correct platform
                            if (
                                args.platform is not None
                                and target.platform != args.platform
                            ):
                                continue

                            progress.update(
                                task, status=f"trying [cyan]{implant.source}[/cyan]"
                            )

                            # Attempt to trigger a new session
                            try:
                                session = implant.trigger(manager, target)
                                manager.target = session
                                used_implant = implant
                                break
                            except ModuleFailed:
                                continue

                    if manager.target is not None:
                        manager.target.log(
                            f"connected via {used_implant.title(manager.target)}"
                        )

                if manager.target is None:
                    manager.create_session(
                        platform=args.platform,
                        protocol=protocol,
                        user=user,
                        password=password,
                        host=host,
                        port=port,
                        identity=args.identity,
                    )

            manager.interactive()


if __name__ == "__main__":

    main()

    sys.exit(0)

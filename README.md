# pwncat

pwncat is a raw bind and reverse shell handler. It streamlines common red team 
operations and all staging code is from your own attacker machine, not the target.

After receiving a connection, **pwncat** will setup some
common configurations when working with remote shells.

- Unset the `HISTFILE` environment variable to disable command history
- Normalize shell prompt
- Locate useful binaries (using `which`)
- Attempt to spawn a pseudoterminal (pty) for a full interactive session

`pwncat` knows how to spawn pty's with a few different methods and will
cross-reference the methods with the executables previously enumerated. After
spawning a pty, it will setup the controlling terminal in raw mode, so you can
interact in a similar fashion to `ssh`. 

`pwncat` will also synchronize the remote pty settings (such as rows, columns,
`TERM` environment variable) with your local settings to ensure the shell
behaves correctly.

To showcase a little bit of the cool functionality, I have recorded a short
[asciinema cast](https://asciinema.org/a/YFF84YCJfp9tQHhTuGkA2PJ4T).

pwncat [documentation] is being built out on Read the Docs. Head there for
the latest usage and development documentation!

## Install

`pwncat` only depends on a working Python development environment. In order
to install some of the packages required with `pip`, you will likely need
your distribution's "Python Development" package. On Debian based systems,
this is `python-dev`. For Arch, the development files are shipped with the
main Python repository. For Enterprise Linux, the package is named 
`python-devel`.

`pwncat` is configured as a standard python package with `distutils`. You
can install `pwncat` directly from GitHub with:

```shell script
pip install git+https://github.com/calebstewart/pwncat.git
```

Or, you can install after cloning the repository with:

```shell script
python setup.py install
```

`pwncat` depends on a custom fork of both `prompt_toolkit` and `paramiko`. 
The forks of these repositories simply added some small features which
weren't accessible in published releases. Pull requests have been submitted
upstream, but until they are (hopefully) merged, `pwncat` will continue to
explicitly reference these forks. As a result, it is recommended to run
`pwncat` from within a virtual environment in order to not pollute your
system environment with the custom packages. To setup a virtual environment
and install `pwncat`, you can use:

```shell script
python3 -m venv pwncat-env
source pwncat-env/bin/activate
python setup.py install
```

If you would like to develop custom privilege escalation or persistence
modules, we recommend you use the `develop` target vice the `install` target
for `setup.py`. This allows changes to the local repository to immediately
be observed with your installed package.

## Features and Functionality

`pwncat` provides two main features. At it's core, it's goal is to automatically
setup a remote PseudoTerminal (pty) which allows interaction with the remote 
host much like a full SSH session. When operating in a pty, you can use common
features of your remote shell such as history, line editing, and graphical
terminal applications.

The other half of `pwncat` is a framework which utilizes your remote shell to
perform automated enumeration, persistence and privilege escalation tasks. The
local `pwncat` prompt provides a number of useful features for standard
penetration tests including:

* File upload and download
* Automated privilege escalation enumeration
* Automated privielge escalation execution
* Automated persistence installation/removal
* Automated tracking of modified/created files
    * `pwncat` also offers the ability to revert these remote "tampers" automatically

The underlying framework for interacting with the remote host aims to abstract
away the underlying shell and connection method as much as possible, allowing
commands and plugins to interact seamlessly with the remote host.

You can learn more about interacting with `pwncat` and about the underlying framework
in the [documentation]. If you have an idea for a
new privilege escalation method or persistence method, please take a look at the
API documentation specifically. Pull requests are welcome!

## Planned Features

**pwncat** would like to be come a red team swiss army knife. Hopefully soon,
more features will be added.

* More privilege escalation methods (sudo -u#-1 CVE, LXD containers, etc.)
* Persistence methods (bind shell, cronjobs, SSH access, PAM abuse, etc.)
* Aggression methods (spam randomness to terminals, flush firewall, etc.)
* Meme methods (terminal-parrot, cowsay, wall, etc.)
* Network methods (port forward, internet access through host, etc.)

[documentation]: https://pwncat.readthedocs.io/en/latest
#!/usr/bin/env python3

import logging
import time
from os import path

import click
from cdswjoblauncher.cdsw.cdsw_common import PythonModuleMode
from rich import print as rich_print, box
from rich.table import Table


from cdswjoblauncher.core.config import Config
from cdswjoblauncher.core.context import CdswLauncherContext
from cdswjoblauncher.core.error import ConfigSetupException, CdswLauncherException
from cdswjoblauncher.core.handler import MainCommandHandler

logger = logging.getLogger(__name__)


@click.group()
@click.option('-c', '--config', default='config.json', help='path to config file')
@click.option('-d', '--debug', is_flag=True, help='turn on DEBUG level logging')
@click.pass_context
def cli(ctx, config: str, debug: bool):
    if ctx.invoked_subcommand == "usage":
        return

    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=level)
    sh_log = logging.getLogger("sh")
    sh_log.setLevel(logging.CRITICAL)
    ctx.ensure_object(dict)
    ctx.obj['loglevel'] = level

    logger.info("Invoked command %s", ctx.invoked_subcommand)

    if ctx.invoked_subcommand == "init":
        cdsw_context = CdswLauncherContext(config_path=config)
        ctx.obj['handler'] = MainCommandHandler(cdsw_context)
        return

    if not path.exists(config):
        raise ConfigSetupException("Config file does not exist. Create config with 'init' subcommand.")

    with open(config) as file:
        json_str = file.read()
        config_file = Config.from_json(json_str)

    context = CdswLauncherContext(config=config_file, config_path=config)
    ctx.obj['handler'] = MainCommandHandler(context)


@cli.command()
@click.pass_context
def init(ctx):
    """
    Initializes an empty config
    """
    handler: MainCommandHandler = ctx.obj['handler']
    config_path = handler.ctx.config_path
    if not path.exists(config_path):
        with open(config_path, 'w') as f:
            f.write(Config().to_json())

        logger.info("Initialized config file {}".format(config_path))
    else:
        logger.info("Config already exists")


@cli.command()
@click.pass_context
@click.argument("package")
@click.option('--execution-mode', required=True, help='Execution mode, will be passed back to the package, arbitrary string from the perspective of this app')
@click.option('--python-module-mode', required=True, type=click.Choice([m.name.lower() for m in PythonModuleMode]), help='Python module mode')
@click.option('--force-reinstall', is_flag=True, help='Whether to force-reinstall package')
def initial_setup(ctx, package: str, execution_mode: str, python_module_mode: str, force_reinstall: bool):
    """
    Sets up project on CDSW
    """
    module_mode = PythonModuleMode[python_module_mode.upper()]

    handler: MainCommandHandler = ctx.obj['handler']
    handler.initial_setup(package, execution_mode, module_mode, force_reinstall)




@cli.command()
@click.option('-n', '--no-wrap', is_flag=True, help='Turns off the wrapping')
def usage(no_wrap: bool = False):
    """
    Prints the aggregated usage of CDSW Job Launcher
    """
    table = Table(title="CDSW Launcher CLI", show_lines=True, box=box.SQUARE)
    table.add_column("Command")
    table.add_column("Description")
    table.add_column("Options", no_wrap=no_wrap)

    def recursive_help(cmd, parent=None, is_root: bool = False):
        ctx = click.core.Context(cmd, info_name=cmd.name, parent=parent)
        commands = getattr(cmd, 'commands', {})
        help = list(filter(bool, cmd.get_help(ctx).split("\n")))
        if is_root:
            command = help[0]
            cmd_id = help.index("Commands:")
            desc = "\n".join(help[2:cmd_id])
            options = "\n".join(help[cmd_id + 1:])
        else:
            command = help[0]
            desc = help[1]
            options = "\n".join(help[3:])
            table.add_row(command, desc, options)

        for sub in commands.values():
            recursive_help(sub, ctx)

    recursive_help(cli, is_root=True)
    rich_print(table)



if __name__ == "__main__":
    logger.info("Started application")
    before = time.time()
    try:
        cli()
        after = time.time()
        logger.info("Executed successfully after %d seconds", int(after - before))
    except CdswLauncherException as e:
        # logger.error(str(e))
        logger.exception(e)
        after = time.time()
        logger.info("Error during execution after %d seconds", int(after - before))
        exit(1)

import logging
import os
import sys
from pathlib import Path
from typing import cast

import click
import click_pathlib
from rich.console import Console
from rich.emoji import Emoji
from rich.logging import RichHandler
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from isomodder import (
    AutoInstallBuilder,
    IsoFile,
    IsoModderFatalException,
    ProgressReporter,
    UbuntuServerIsoFetcher,
)

MIN_PYTHON = (3, 6)
if sys.version_info < MIN_PYTHON:
    sys.exit("Python %s.%s or later is required.\n" % MIN_PYTHON)


def get_rich() -> Progress:
    return Progress(
        TextColumn("[bold blue]{task.description}", justify="right"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•",
        DownloadColumn(),
        "•",
        TransferSpeedColumn(),
        "•",
        TimeRemainingColumn(),
    )


console = Console()

logging.basicConfig(level="NOTSET", format="%(message)s", datefmt="[%X]", handlers=[RichHandler()])


class EnumChoice(click.Choice):
    def __init__(self, enum, case_sensitive=False, use_value=False):
        self.enum = enum
        self.use_value = use_value
        choices = [str(e.value) if use_value else e.name for e in self.enum]
        super().__init__(choices, case_sensitive)

    def convert(self, value, param, ctx):
        try:
            return self.enum[value]
        except KeyError:
            pass

        result = super().convert(value, param, ctx)
        # Find the original case in the enum
        if not self.case_sensitive and result not in self.choices:
            result = next(c for c in self.choices if result.lower() == c.lower())
        if self.use_value:
            return next(e for e in self.enum if str(e.value) == result)
        return self.enum[result]


def get_default_cache_dir() -> str:
    xdg_cache_home = Path(os.environ.get("XDG_CACHE_HOME", f"{os.environ['HOME']}/.cache"))
    app_cache = xdg_cache_home / "ubautoiso"
    app_cache.mkdir(parents=True, exist_ok=True)
    return str(app_cache)


def get_default_output_file() -> str:
    output_file = Path.cwd() / "autoinstall.iso"
    return str(output_file)


@click.command()
@click.option(
    "-o",
    "--output",
    type=click_pathlib.Path(),
    default=get_default_output_file,
    show_default="$CWD/autoinstall.iso",
)
@click.option(
    "-c",
    "--cache-dir",
    type=click_pathlib.Path(exists=True, file_okay=False, writable=True),
    default=get_default_cache_dir,
    show_default="$XDG_CACHE_HOME/ubautoiso",
)
@click.option("-r", "--release", default="20.04", show_default=True)
@click.option("--no-prompt", is_flag=True)
@click.option("--no-mbr", is_flag=True)
@click.option("--no-efi", is_flag=True)
@click.argument("autoinstall_file", type=click_pathlib.Path(exists=True, dir_okay=False, readable=True))
def cli(output, cache_dir, prompt, autoinstall_file, no_efi, no_mbr):
    fetcher = UbuntuServerIsoFetcher(working_dir=cache_dir, release="20.04")
    with get_rich() as progress:
        iso_path = fetcher.fetch(cast(ProgressReporter, progress))
    iso_file = IsoFile(iso_path)
    builder = AutoInstallBuilder(
        source_iso=iso_file,
        autoinstall_yaml=autoinstall_file,
        grub_entry_stamp="paranoidNAS AutoInstall",
        autoinstall_prompt=prompt,
        supports_efi=(not no_efi),
        supports_mbr=(not no_mbr),
    )

    builder.build()

    if output.exists():
        output.unlink()
    with get_rich() as progress:
        iso_file.write_iso(output, cast(ProgressReporter, progress))

    logging.info(f"You're ready to burn! {Emoji('fire')}")

    # print out info here


def main():
    try:
        cli()
    except SystemExit:
        pass
    except IsoModderFatalException as exc:
        console.print()
        console.print(f":cross_mark: [bold red] {exc} :cross_mark:")
        console.print()
    except BaseException:
        console.print()
        console.print(
            ":pile_of_poo: :whale: [bold red] Something totally unexpected has happened. Let's see..."
        )
        console.print()
        console.print_exception()
        console.print()


if __name__ == "__main__":
    main()

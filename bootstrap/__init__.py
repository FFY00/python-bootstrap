# SPDX-License-Identifier: MIT

import atexit
import logging
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

from collections.abc import Collection, Mapping, Sequence
from typing import NamedTuple, Optional, Tuple


class Package(NamedTuple):
    srcdir: pathlib.Path
    module_path: pathlib.Path
    module_sources: Collection[str]


ROOT = pathlib.Path(__file__).parent.parent
WORKING_DIR = ROOT / '.bootstrap'
MODULES = WORKING_DIR / 'modules'
TMPDIR = WORKING_DIR / 'tmp'
EXTERNAL = ROOT / 'external'

PACKAGES = {
    # what we need
    'build': Package(
        EXTERNAL / 'build',
        EXTERNAL / 'build' / 'src',
        {'build'},
    ),
    'installer': Package(
        EXTERNAL / 'installer',
        EXTERNAL / 'installer' / 'src',
        {'installer'},
    ),
    # dependencies
    'setuptools': Package(
        EXTERNAL / 'setuptools',
        EXTERNAL / 'setuptools',
        {'setuptools', 'pkg_resources', '_distutils_hack'},
    ),
    'flit_core': Package(
        EXTERNAL / 'flit' / 'flit_core',
        EXTERNAL / 'flit' / 'flit_core',
        {'flit_core'},
    ),
    'wheel': Package(
        EXTERNAL / 'wheel',
        EXTERNAL / 'wheel' / 'src',
        {'wheel'},
    ),
    'tomli': Package(
        EXTERNAL / 'tomli',
        EXTERNAL / 'tomli',
        {'tomli'},
    ),
    'pep517': Package(
        EXTERNAL / 'pep517',
        EXTERNAL / 'pep517',
        {'pep517'},
    ),
}

EXTRA_PATH = [str(package.module_path) for package in PACKAGES.values()]
PACKAGE_PATH_ENV = {
    'PYTHONPATH': os.path.pathsep.join(EXTRA_PATH),
}


# copy sources to module dir and inject it into sys.path
MODULES.mkdir(parents=True)
for package in PACKAGES.values():
    for path in package.module_sources:
        shutil.copytree(
            package.module_path / path,
            MODULES / path,
        )
atexit.register(shutil.rmtree, MODULES)
sys.path.insert(0, str(MODULES))


# import what we need from the inject modules
import build  # noqa: E402
import build.env  # noqa: E402
import pep517  # noqa: E402


_logger = logging.getLogger(__name__)


def log(msg):
    _logger.info(msg)


def custom_runner(
    cmd: Sequence[str],
    cwd: Optional[str] = None,
    extra_environ: Optional[Mapping[str, str]] = None,
) -> None:
    extra_environ = dict(extra_environ) if extra_environ else {}
    extra_environ.update(PACKAGE_PATH_ENV)
    pep517.default_subprocess_runner(cmd, cwd, extra_environ)


def install_package_egginfo(name: str) -> None:
    package = PACKAGES[name]
    subprocess.check_call(
        [sys.executable, 'setup.py', 'egg_info'],
        env=os.environ | PACKAGE_PATH_ENV,
        cwd=package.srcdir,
    )
    shutil.copytree(
        package.module_path / f'{name}.egg-info',
        MODULES / f'{name}.egg-info',
    )


def build_package(name: str, outdir: pathlib.Path) -> pathlib.Path:
    log(f'Building {name}...')
    srcdir = PACKAGES[name].srcdir
    builder = build.ProjectBuilder(str(srcdir), runner=custom_runner)
    wheel = builder.build('wheel', str(outdir))
    return pathlib.Path(wheel)

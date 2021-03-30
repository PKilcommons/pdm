import os
import sys
import venv
from pathlib import Path
from typing import Callable

import distlib.wheel
import pytest
from pytest_mock.plugin import MockerFixture

from pdm.core import Core
from pdm.models.requirements import filter_requirements_with_extras
from pdm.pep517.api import build_wheel
from pdm.project import Project
from pdm.utils import cd, temp_environ
from tests.conftest import TestProject


def test_project_python_with_pyenv_support(
    project: TestProject, mocker: MockerFixture
) -> None:
    from pythonfinder.environment import PYENV_ROOT

    del project.project_config["python.path"]
    project._python_executable = None
    pyenv_python = Path(PYENV_ROOT, "shims", "python")
    with temp_environ():
        os.environ["PDM_IGNORE_SAVED_PYTHON"] = "1"
        mocker.patch("pdm.project.core.PYENV_INSTALLED", True)
        mocker.patch(
            "pythonfinder.models.python.get_python_version",
            return_value="3.8.0",
        )
        assert Path(project.python_executable) == pyenv_python

        # Clean cache
        project._python_executable = None

        project.project_config["python.use_pyenv"] = False
        assert Path(project.python_executable) != pyenv_python


def test_project_config_items(project: TestProject) -> None:
    config = project.config

    for item in ("python.use_pyenv", "pypi.url", "cache_dir"):
        assert item in config


def test_project_config_set_invalid_key(project: TestProject) -> None:
    config = project.project_config

    with pytest.raises(KeyError):
        config["foo"] = "bar"


def test_project_sources_overriding(project: TestProject) -> None:
    project.project_config["pypi.url"] = "https://testpypi.org/simple"
    assert project.sources[0]["url"] == "https://testpypi.org/simple"

    project.tool_settings["source"] = [
        {"url": "https://example.org/simple", "name": "pypi", "verify_ssl": True}
    ]
    assert project.sources[0]["url"] == "https://example.org/simple"


def test_global_project(tmp_path: Path, core: Core) -> None:
    project = Project.create_global(tmp_path.as_posix())
    project.core = core
    project.init_global_project()
    assert project.environment.is_global


def test_project_use_venv(project: TestProject) -> None:
    del project.project_config["python.path"]
    project._python_executable = None
    scripts = "Scripts" if os.name == "nt" else "bin"
    suffix = ".exe" if os.name == "nt" else ""
    venv.create(project.root / "venv")

    project.project_config["use_venv"] = True
    env = project.environment
    assert (
        Path(env.python_executable)
        == project.root / "venv" / scripts / f"python{suffix}"
    )
    assert env.is_global


def test_project_with_combined_extras(
    fixture_project: Callable[[str], TestProject]
) -> None:
    project = fixture_project("demo-combined-extras")
    (project.root / "build").mkdir(exist_ok=True)
    with cd(project.root.as_posix()):
        wheel_name = build_wheel(str(project.root / "build"))
        wheel = distlib.wheel.Wheel(str(project.root / "build" / wheel_name))

    all_requires = filter_requirements_with_extras(
        wheel.metadata.run_requires, ("all",)
    )
    for dep in ("urllib3", "chardet", "idna"):
        assert dep in all_requires


def test_project_packages_path(project: TestProject) -> None:
    packages_path = project.environment.packages_path
    version = ".".join(map(str, sys.version_info[:2]))
    if os.name == "nt" and sys.maxsize <= 2 ** 32:
        assert packages_path.name == version + "-32"
    else:
        assert packages_path.name == version


def test_project_auto_detect_venv(project: TestProject) -> None:

    venv.create(project.root / "test_venv")

    scripts = "Scripts" if os.name == "nt" else "bin"
    suffix = ".exe" if os.name == "nt" else ""

    project.project_config["use_venv"] = True
    project._python_executable = None
    project.project_config["python.path"] = (
        project.root / "test_venv" / scripts / f"python{suffix}"
    ).as_posix()

    assert project.environment.is_global


def test_ignore_saved_python(project: TestProject) -> None:
    project.project_config["use_venv"] = True
    project._python_executable = None
    scripts = "Scripts" if os.name == "nt" else "bin"
    suffix = ".exe" if os.name == "nt" else ""
    venv.create(project.root / "venv")
    with temp_environ():
        os.environ["PDM_IGNORE_SAVED_PYTHON"] = "1"
        assert Path(project.python_executable) != project.project_config["python.path"]
        assert (
            Path(project.python_executable)
            == project.root / "venv" / scripts / f"python{suffix}"
        )

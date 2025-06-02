import logging
import os
import re
import sys

script_dir: str = os.path.dirname(os.path.realpath(__file__))
repo_dir: str = os.path.dirname(script_dir)


def check_dependencies_synced():
    r"""Check that the dependencies of environment.yml, meta.yaml and pyproject.toml are in sync."""
    conda_env = open(os.path.join(repo_dir, "environment.yml"), "r").read()
    pyproject_toml = open(os.path.join(repo_dir, "pyproject.toml"), "r").read()
    conda_recipe = open(os.path.join(repo_dir, "conda.recipe", "meta.yaml"), "r").read()

    # check for MagnetismReflectometer versions
    mr_conda = re.search(r"mr_reduction[>=<]+(\d+(?:\.\d+)*)", conda_env).group(1)
    mr_pyproject = re.search(r"mr_reduction[>=<]+(\d+(?:\.\d+)*)", pyproject_toml).group(1)
    mr_recipe = re.search(r"mr_reduction[>=<]+(\d+(?:\.\d+)*)", conda_recipe).group(1)
    if mr_conda != mr_pyproject:
        raise RuntimeError("environment.yml and pyproject.toml ask different versions of mr_reduction")
    if mr_conda != mr_recipe:
        raise RuntimeError("environment.yml and meta.yaml ask different versions of mr_reduction")


if __name__ == "__main__":
    try:
        check_dependencies_synced()
    except RuntimeError as e:
        logging.error(f"{e}")
        sys.exit(1)
    sys.exit(0)

<!-- Badges -->

![Build Status](https://github.uom/neutrons/quicknxs/actions/workflows/package.yml/badge.svg)
![Test Pipeline](https://github.com/neutrons/quicknxs/actions/workflows/test.yml/badge.svg)
[![Documentation Status](https://readthedocs.org/projects/reflectivity-ui/badge/?version=latest)](https://reflectivity-ui.readthedocs.io/en/latest/?badge=latest)
[![codecov](https://codecov.io/gh/neutrons/quicknxs/branch/master/graph/badge.svg)](https://codecov.io/gh/neutrons/quicknxs)

<!-- End Badges -->

# QuickNXS

This app is a frontend for Magnetic Reflectivity Reduction.

# Install

## Install the development environment

```bash
conda env create -f environment.yml
activate quicknxs
```

## Install QuickNXS

### Install via source

```bash
python -m pip install -e .
```

This installs the code in [editable mode](https://pip.pypa.io/en/stable/cli/pip_install/#cmdoption-e>).

### Build the wheel

Once QuickNXS is installed

```bash
python -m build --no-isolation --wheel
```

now you can install QuickNXS via the generated wheel on other system

```bash
python3 -m pip install quicknxs*.whl
```

## Run

To launch the QuickNXS GUI, run the following command:

```bash
quicknxs-gui
```

When trying to run the GUI, you may see the following error:
```bash
GLib-GIO-ERROR **: 13:35:06.773: Settings schema 'org.gnome.settings-daemon.plugins.xsettings' does not contain a key named 'antialiasing'
```

In this case, try setting the `GDK_BACKEND` environment variable to `x11` before running the GUI:
```bash
GDK_BACKEND=x11 quicknxs-gui
```

## Test

In order to run the tests, you will need to have cloned the [test data submodule](https://reflectivity-ui.readthedocs.io/en/latest/developer/environment.html#test-data), which requires `git-lfs` to be installed.
Once you have `git-lfs` installed, you can clone the submodule with the following command:

```bash
git submodule update --init --recursive
```

Then you can run the tests with the following command:

```bash
pytest
```

<!-- Badges -->

![Build Status](https://github.uom/neutrons/quicknxs/actions/workflows/package.yml/badge.svg)
![Test Pipeline](https://github.com/neutrons/quicknxs/actions/workflows/test.yml/badge.svg)
[![Documentation Status](https://readthedocs.org/projects/reflectivity-ui/badge/?version=latest)](https://reflectivity-ui.readthedocs.io/en/latest/?badge=latest)
[![codecov](https://codecov.io/gh/neutrons/quicknxs/branch/master/graph/badge.svg)](https://codecov.io/gh/neutrons/quicknxs)

<!-- End Badges -->

# QuickNXS

A PyQT GUI for Magnetic Reflectivity Reduction.

This project uses [Pixi](https://pixi.sh/) as the single tool for managing environments, dependencies, packaging, and task execution.

## Installation

1. If you don't already have it, install [Pixi](https://pixi.sh/):

   ```bash
   curl -fsSL https://pixi.sh/install.sh | bash
   ```

2. Create the virtual environment

   ```bash
   pixi install
   ```

3. Activate the virtual environment

   ```bash
   pixi shell
   ```

## Run

The GUI is now available as a command-line tool. You can run it directly either from the virtual environment or by using the `pixi` command:

```bash
pixi shell
quicknxs-gui
```

or simply:

```bash
pixi run quicknxs-gui
```

## Testing

In order to run the tests, you will need to have cloned the [test data submodule](https://reflectivity-ui.readthedocs.io/en/latest/developer/environment.html#test-data), which requires `git-lfs` to be installed.
Once you have `git-lfs` installed, you can clone the submodule with the following command:

```bash
git submodule update --init --recursive
```

Then you can run the tests with the following command:

```bash
pixi run test
```

## Troubleshooting

When trying to run the GUI, you may see the following error:

```bash
GLib-GIO-ERROR **: 13:35:06.773: Settings schema 'org.gnome.settings-daemon.plugins.xsettings' does not contain a key named 'antialiasing'
```

In this case, try setting the `GDK_BACKEND` environment variable to `x11` before running the GUI:

```bash
GDK_BACKEND=x11 quicknxs-gui
```

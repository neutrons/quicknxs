<!-- Badges -->

![Build Status](https://github.com/neutrons/reflectivity_ui/actions/workflows/actions.yml/badge.svg)
[![Documentation Status](https://readthedocs.org/projects/reflectivity-ui/badge/?version=latest)](https://reflectivity-ui.readthedocs.io/en/latest/?badge=latest)
[![codecov](https://codecov.io/gh/neutrons/reflectivity_ui/branch/master/graph/badge.svg)](https://codecov.io/gh/neutrons/reflectivity_ui)

<!-- End Badges -->

# QuickNXS

This app is a frontend for Magnetic Reflectivity Reduction.

# Install

## Install the development environment

``` bash
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
python3 -m pip install reflectivity_ui*.whl
```

## Run

```bash
bin/quicknxs2
```

## Test

Work in progress.

.. _development_environment:

Development Environment
=======================

.. contents::
    :local:


Setup Local Development Environment
-----------------------------------

To setup a local development environment, the developers should follow the steps below:

* Install ``anaconda`` (``miniconda`` is recommended)
* Clone the repository and make a feature branch based off ``next``.
* Create a new virtual environment with ``conda env create`` which uses ``environment.yml``

.. code-block:: sh

   conda env create --file environment.yml

* Activate the virtual environment with ``conda activate quicknxs``
* Activate the pre-commit hooks

.. code-block:: sh

   pre-commit install


The ``environment.yml`` contains all of the dependencies for both the developer and the build servers.
Update file ``environment.yml`` if dependencies are added to the package.




.. _developing_with_pycharm:

Developing with PyCharm
-----------------------
Currently, QuickNXS contains PyQt5 and PiSide6 which are not compatible with each other
and therefore one must be selected as the default bindings to Qt.
Open the PyCharm settings and select `PyQt5` as the default bindings to Qt in the `python debugger`.

.. figure:: ./media/debugging_pycharmm_1.png
   :align: center
   :width: 800



.. _test-data:

Test Data
---------

The test data will be stored in a second git repository
`quicknxs-data <https://code.ornl.gov/sns-hfir-scse/infrastructure/test-dataquicknxs-data>`_
which uses git-lfs.
To use it, first install git-lfs, then setup the git-submodule

.. code-block:: sh

   git submodule init
   git submodule update

See also :doc:`how to write integration tests <integration_test>`

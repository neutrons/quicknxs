=====================
How to Make a Release
=====================

.. contents::
    :local:


Candidate and Production Releases
---------------------------------
- Follow the `Software Release Process <https://ornl-neutrons.atlassian.net/wiki/x/AYBkAQ>`_
  for continuous versioning, as well as creating Candidate and Production releases.\
- Then create a new Release Candidate (rc) just to include these changes in the release.


Conda Package
-------------

Candidate and Production releases ``quicknxs`` are automatically released to the project channel
`neutrons`_ whenever a new tag is pushed to the repository.

To manually build a conda package (for testing purposes only),
a pixi task is included for convenience. Simply run:

.. code-block:: sh

    pixi run conda-build

.. _neutrons: https://anaconda.org/neutrons

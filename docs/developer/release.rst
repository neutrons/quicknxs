=====================
How to Make a Release
=====================

.. contents::
    :local:


Candidate and Production Releases
---------------------------------
- Follow the `Software Maturity Model <https://ornl-neutrons.atlassian.net/wiki/spaces/NDPD/pages/23363585/Software+Maturity+Model>`_
  for continuous versioning, as well as creating Candidate and Production releases.\
- Right before a Major or Minor release, update the release notes file ``docs/release_notes.rst``.
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

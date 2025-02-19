.. _integration_test:

How to Write Integration Tests
==============================

The Data Repository
===================

Integration tests will typically require data from the **data repository**
located in `quicknxs/tests/data/quicknxs-data/` as a
`git submodule <https://git-scm.com/book/en/v2/Git-Tools-Submodules>`_.

Git Submodule
-------------

**tutorials:**

- `atlassian <https://www.atlassian.com/git/tutorials/git-submodule>`_
- `sitepoint <https://www.sitepoint.com/git-submodules-introduction/>`_

**typical commands:**

Here, "submodule" refers to repo `quicknxs-data` and "parent" refers to repo `quicknxs`

- checkout the submodule after cloning the parent with command `git submodule init`
- find the refspec stored in the parent with command `git ls-tree $(git branch --show-current) tests/data/quicknxs-data`
- synchronize the submodule to the refspec stored in the parent with command `git submodule update`
- after making commits in the sumodule, synchronize the refspec stored in the parent with commands `git add...` and `git commit...`

Pytest Fixtures
===============

Pytest fixtures in `conftest.py` providing directories frequently accessed:

+--------------+----------------------------------------------------------------------------+
| Fixture      | Value (as a `pathlib.Path` object)                                         |
+==============+============================================================================+
| DATA_DIR     | quicknxs/tests/data/quicknxs-data                                          |
+--------------+----------------------------------------------------------------------------+


Writing Test Functions
======================

Test functions accessing `DATA_DIR` should be marked with the `datarepo` marker

.. code:: python

   @pytest.mark.datarepo
   def test_function(DATA_DIR):
       pass

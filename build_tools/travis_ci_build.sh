#!/bin/sh
python setup.py install
coverage run test/data_handling_test.py
pylint --rcfile build_tools/pylint.rc -f parseable quicknxs/interfaces/data_handling quicknxs/interfaces/event_handlers

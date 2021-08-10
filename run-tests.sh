#!/usr/bin/env bash
# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 CESNET.
#
# OARepo-S3-CLI is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.


# Usage:
#   ./run-tests.sh

# Quit on errors
set -o errexit

# Quit on unbound symbols
set -o nounset
#python -m check_manifest --ignore ".*-requirements.txt"
python -m pytest "$@"
tests_exit_code=$?
exit "$tests_exit_code"

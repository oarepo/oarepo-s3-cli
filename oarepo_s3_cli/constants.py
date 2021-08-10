# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 CESNET
#
# OARepo-S3-CLI is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.
""" OARepo S3 client constants. """

import multiprocessing as mp


MIB_5 = 5*1024*1024
MIN_PART_SIZE = MIB_5
MAX_PART_SIZE = MIB_5 * 5
MAX_PARTS = 1000000
MAX_PARALLEL = mp.cpu_count()
MAX_RETRIES = 5

CYCLE_SLEEP = 1    # progress bar refresh interval
RETRY_SLEEP = 2    # sleep(RETRY_SLEEP * retry)
MON_TIMEOUT = 3600
WORKER_TIMEOUT = 60
FORCED_GET_TIMEOUT = 0.1

BAR_LENGTH = 20

STATUS_OK=0
STATUS_ERR_MAX_RETRIES=1
STATUS_CLICK=2
STATUS_KILLED=3
STATUS_EMPTY_PART_RESULT=4
STATUS_WRONG_FILE=5
STATUS_GENERAL_ERROR=6
STATUS_EXPIRED_TOKEN=7
STATUS_INVALID_TOKEN=8
STATUS_WRONG_SERVER_RESPONSE=9
STATUS_UNKNOWN=10
STATUS_UPLOAD_UNCOMPLETED=11

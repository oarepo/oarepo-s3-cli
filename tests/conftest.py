# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 CESNET.
#
# OARepo-S3-CLI is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.

"""Pytest configuration."""

import hashlib, pytest, string, random, urllib3
from unittest.mock import Mock

fake_file_size = 1024
fake_data = ''.join(random.choices(string.hexdigits, k=fake_file_size))
m = hashlib.blake2b()
m.update(fake_data.encode())
fake_file_info = Mock(
    size=fake_file_size,
    filename=''.join(random.choices(string.hexdigits, k=8)),
    data=fake_data,
    hash_blake2b=m.hexdigest()
)

@pytest.fixture(scope='module')
def urllib3_reconf():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

@pytest.fixture(scope='module')
def mock_oarepo():
    r = Mock(
        url='https://127.0.0.1:5555',
        token='abcd1234',
        pid=1,
        key='testfile.dat',
        s3key='mockS3key',
        uploadId='mockUploadId',
        partNum=1,
        ETag='mockETag'
    )
    return r

@pytest.fixture(scope='module')
def fake_file():
    return fake_file_info

class MockPoolApplyResults:
    def __init__(self, func, args, callback=None):
        print(f'MockPoolApplyResults: {args}')
        self.res = func(*args)
        callback(self.res)

    def get(self, timeout=0):
        return self.res

def mock_apply_async_func(self, func, args=(), kwds=(), callback=None, error_callback=None):
    print(f'mock_apply_async: {args}')
    apres = MockPoolApplyResults(func, args, callback=callback)
    return apres


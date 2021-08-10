# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 CESNET.
#
# OARepo-S3-CLI is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.

"""Module tests."""
import pytest

from oarepo_s3_cli.utils import *
from oarepo_s3_cli.constants import *

def test_get_file_chunk_size():
    """ Test get_file_chunk_size"""
    assert get_file_chunk_size(1) == (1, 1, 1)
    assert get_file_chunk_size(MIB_5) == (1, MIB_5, MIB_5)
    assert get_file_chunk_size(MIB_5+1) == (2, MIB_5, 1)
    assert get_file_chunk_size(MIB_5*5-1) == (5, MIB_5, MIB_5-1)
    assert get_file_chunk_size(MIB_5*5) == (5, MIB_5, MIB_5)
    assert get_file_chunk_size(MIB_5*5+1) == (6, MIB_5, 1)
    assert get_file_chunk_size(MIB_5*MAX_PARTS) == (MAX_PARTS, MIB_5, MIB_5)
    assert get_file_chunk_size(MIB_5*MAX_PARTS+1) == (MAX_PARTS/5+1, MIB_5*5, 1)
    assert get_file_chunk_size(MIB_5*MAX_PARTS*2) == (MAX_PARTS*2/5, MIB_5*5, MIB_5*5)
    assert get_file_chunk_size(MIB_5*5*MAX_PARTS) == (MAX_PARTS, MIB_5*5, MIB_5*5)
    with pytest.raises(Exception):
        get_file_chunk_size(MIB_5*5*MAX_PARTS+1)

def test_size_fmt():
    assert size_fmt(999) == '999 B'
    assert size_fmt(1023) == '1023 B'
    assert size_fmt(1025) == '1 KiB'
    assert size_fmt(1024*999) == '999 KiB'
    assert size_fmt(1024*1023) == '1023 KiB'
    assert size_fmt(1024*1024) == '1 MiB'
    assert size_fmt(1024*1024*1023) == '1023 MiB'
    assert size_fmt(1024*1024*1025) == '1 GiB'
    assert size_fmt(1024*1024*1024*1024) == '1 TiB'

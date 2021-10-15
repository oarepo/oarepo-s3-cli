# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 CESNET.
#
# OARepo-S3-CLI is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.

"""Module tests."""
import pytest, responses
from unittest import mock

from oarepo_s3_cli.utils import *
from oarepo_s3_cli.constants import *
from tests.conftest import fake_file_info
from oarepo_s3_cli.lib import OARepoS3Client

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

@responses.activate
@mock.patch('builtins.open', new_callable=mock.mock_open, read_data=fake_file_info.data)
@mock.patch('os.access')
@mock.patch('os.path.exists')
@mock.patch('os.path.isfile')
@mock.patch('os.path.getsize')
def test_hash_file(mock_path_getsize, mock_path_isfile, mock_path_exists, mock_os_access, mock_open, mock_oarepo):
    test_size = fake_file_info.size
    test_filename = fake_file_info.filename

    token_status_url = f"{mock_oarepo.url}/access-tokens/status"
    responses.add(responses.GET, token_status_url, status=200,
        json={
            'status': 'OK',
            'links': {
                'files': f'{mock_oarepo.url}/draft/records/1/files/'
            }
        }
    )
    oas3 = OARepoS3Client(mock_oarepo.url, mock_oarepo.token, parallel=1, quiet=False)
    assert isinstance(oas3, OARepoS3Client)
    assert oas3.url == mock_oarepo.url

    mock_os_access.side_effect = lambda fn, mode: fn == test_filename
    mock_path_exists.side_effect = lambda fn: fn == test_filename
    mock_path_isfile.side_effect = lambda fn: fn == test_filename
    mock_path_getsize.side_effect = lambda fn: test_size if fn == test_filename else FileNotFoundError
    oas3.set_file(test_filename, mock_oarepo.key)
    oas3.urlFiles = oas3.check_token_status(mock_oarepo.token)
    file_url = f"{oas3.urlFiles}{mock_oarepo.key}"
    responses.add(responses.GET, file_url, status=200, body=fake_file_info.data)
    with mock.patch('builtins.open', new_callable=mock.mock_open, read_data=fake_file_info.data.encode()):
        local_hash = get_local_hash(fake_file_info.filename)
        assert local_hash == fake_file_info.hash_blake2b
        remote_hash = get_remote_hash(mock_oarepo.token, file_url)
        assert remote_hash == fake_file_info.hash_blake2b
        assert local_hash == remote_hash
        assert (True, STATUS_OK) == oas3.process_click_check(mock_oarepo.key, test_filename)

# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 CESNET.
#
# OARepo-S3-CLI is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.

"""Module lib tests."""

import re
import responses
from unittest import mock

from oarepo_s3_cli.constants import *
from oarepo_s3_cli.lib import OARepoS3Client
from tests.conftest import fake_file_info


@mock.patch('oarepo_s3_cli.lib.requests.get')
def test_check_token_status(mock_get, mock_oarepo):
    mock_get.return_value = mock.Mock(
        status_code=200,
        json=lambda : {
            'status':'OK',
            'links':{
                'files': f'{mock_oarepo.url}/draft/records/1/files/'
            }
        }
    )
    oas3 = OARepoS3Client(mock_oarepo.url, None, parallel=1, quiet=False)
    result = oas3.check_token_status(token=mock_oarepo.token)
    assert re.match(f"^{mock_oarepo.url}/draft/records/[0-9]+/files/$", result, re.MULTILINE|re.DOTALL)

@responses.activate
def test_check_token_status2(mock_oarepo):
    token_status_url = f"{mock_oarepo.url}/access-tokens/status"
    responses.add(responses.GET, token_status_url, status=200,
        json={
            'status': 'OK',
            'links': {
                'files': f'{mock_oarepo.url}/draft/records/1/files/'
            }
        }
    )
    oas3 = OARepoS3Client(mock_oarepo.url, None, parallel=1, quiet=False)
    result = oas3.check_token_status(token=mock_oarepo.token)
    assert re.match(f"^{mock_oarepo.url}/draft/records/[0-9]+/files/$", result, re.MULTILINE|re.DOTALL)

@responses.activate
@mock.patch('os.access')
@mock.patch('os.path.exists')
@mock.patch('os.path.isfile')
@mock.patch('os.path.getsize')
def test_OARepoS3Client(mock_path_getsize, mock_path_isfile, mock_path_exists, mock_os_access, mock_oarepo):
    token_status_url = f"{mock_oarepo.url}/access-tokens/status"
    responses.add(responses.GET, token_status_url, status=200,
        json={
            'status': 'OK',
            'links': {
                'files': f'{mock_oarepo.url}/draft/records/1/files/'
            }
        }
    )
    test_size = fake_file_info.size
    test_filename = fake_file_info.filename
    # test_data = fake_file_info.data
    mock_os_access.side_effect = lambda fn, mode: fn == test_filename
    mock_path_exists.side_effect = lambda fn: fn == test_filename
    mock_path_isfile.side_effect = lambda fn: fn == test_filename
    mock_path_getsize.side_effect = lambda fn: test_size if fn == test_filename else FileNotFoundError

    oas3 = OARepoS3Client(mock_oarepo.url, mock_oarepo.token, parallel=1, quiet=True)
    assert isinstance(oas3, OARepoS3Client)
    assert oas3.url == mock_oarepo.url
    assert oas3.parallel == 1
    assert oas3.quiet == True
    assert oas3.key is None

    oas3.set_file(test_filename)
    assert oas3.file == test_filename
    assert oas3.data_size == test_size
    assert oas3.num_parts == 1
    assert oas3.part_size == test_size

@responses.activate
@mock.patch('builtins.open', new_callable=mock.mock_open, read_data=fake_file_info.data)
@mock.patch('os.access')
@mock.patch('os.path.exists')
@mock.patch('os.path.isfile')
@mock.patch('os.path.getsize')
def test_init_upload(mock_path_getsize, mock_path_isfile, mock_path_exists, mock_os_access, mock_open, mock_oarepo):
    test_size = fake_file_info.size
    test_filename = fake_file_info.filename
    # test_data = fake_file_info.data
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
    oas3.quiet = True
    oas3.token = mock_oarepo.token
    oas3.set_file(test_filename, mock_oarepo.key)
    assert oas3.file == test_filename
    assert oas3.key == mock_oarepo.key
    assert oas3.data_size == test_size
    assert oas3.num_parts == 1
    assert oas3.part_size == test_size

    token_status_url = f"{mock_oarepo.url}/access-tokens/status"
    responses.add(responses.GET, token_status_url, status=200,
        json={
            'status': 'OK',
            'links': {
                'files': f'{mock_oarepo.url}/draft/records/1/files/'
            }
        }
    )
    oas3.urlFiles = oas3.check_token_status(mock_oarepo.token)

    init_url = f"{oas3.urlFiles}?multipart=true"
    responses.add(responses.POST, init_url, status=201,
        json={
            'key': mock_oarepo.s3key,
            'uploadId': mock_oarepo.uploadId
        }
    )
    upload_id = oas3.init_upload()
    assert upload_id == mock_oarepo.uploadId
    assert re.match(f"^{oas3.urlFiles}{mock_oarepo.key}/{upload_id}$", oas3.urlUpload)

    presign_url = f"{oas3.urlUpload}/1/presigned"
    part_s3_url = 'https://mock_part_s3_url.example.org'
    responses.add(responses.GET, presign_url, status=200,
        json={
          'url': part_s3_url,
        }
    )
    responses.add(responses.PUT, part_s3_url, status=201,
        headers={'ETag': mock_oarepo.ETag}
    )
    oas3.quiet = False
    resp = oas3.upload_part(1, 'val')
    assert resp['PartNumber'] == 1
    assert resp['status'] == STATUS_OK
    assert resp['ETag'] == mock_oarepo.ETag

    abort_url = f"{oas3.urlUpload}/abort"
    responses.add(responses.DELETE, abort_url, status=200)
    resp = oas3.abort_upload()
    assert resp.status_code == 200

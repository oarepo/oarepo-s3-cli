# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 CESNET.
#
# OARepo-S3-CLI is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.

"""Module CLI tests."""

import re, string, random, os.path, subprocess, logging
import responses
from click.testing import CliRunner
from unittest import mock
from oarepo_s3_cli.clickdef import cli_main, cli_debug_test
from tests.conftest import fake_file_info, mock_apply_async_func

# logger = logging
# loglevel = logging.DEBUG
# logging.basicConfig(level=loglevel, format='%(message)s')
# logger = logging.getLogger(__name__)


def test_help():
    result = CliRunner().invoke(cli_main, ['--help'])
    assert 0 == result.exit_code
    assert re.match(f"^Usage: .*\n\nOptions:.*\nCommands:.*\n  upload$", result.output, re.MULTILINE|re.DOTALL)
    # assert result.output == ''

def test_upload_help():
    result = CliRunner().invoke(cli_main, ['-t', 'mock_token', '-e', 'mock_url', 'upload', '--help'])
    assert result.exit_code == 0
    assert re.match(f"^Usage: .* upload .*\n\nOptions:.*$", result.output, re.MULTILINE|re.DOTALL)
    # assert result.output == ''

@responses.activate
def test_logTest(mock_oarepo):
    token_status_url = f"{mock_oarepo.url}/access-tokens/status"
    record_url = f'{mock_oarepo.url}/draft/records/{mock_oarepo.pid}'
    files_url = f'{record_url}/files/'
    responses.add(responses.GET, token_status_url, status=200,
        json={
            'status': 'OK',
            'links': {
                'files': files_url
            }
        }
    )
    result = CliRunner(mix_stderr=False).invoke(cli_main, ['-t', 'mock_token', '-d', '-e', mock_oarepo.url, 'debug_test'])
    print(result.output)
    print(result.stderr_bytes)
    assert result.exit_code == 0

@mock.patch('builtins.open', new_callable=mock.mock_open, read_data=fake_file_info.data)
@mock.patch('os.path.exists')
@mock.patch('os.path.isfile')
@mock.patch('os.path.getsize')
def test_mock_open_decor(mock_path_getsize, mock_path_isfile, mock_path_exists, mock_open):
    test_size = fake_file_info.size
    test_filename = fake_file_info.filename
    test_data = fake_file_info.data
    mock_path_exists.side_effect = lambda fn: fn == test_filename
    mock_path_isfile.side_effect = lambda fn: fn == test_filename
    mock_path_getsize.side_effect = lambda fn: test_size if fn == test_filename else FileNotFoundError
    with open(test_filename) as h:
        r = h.read()
        assert r == test_data
        assert len(r) == test_size
    assert os.path.exists(test_filename)
    assert os.path.isfile(test_filename)
    assert os.path.getsize(test_filename) == test_size


@responses.activate
@mock.patch('multiprocessing.pool.Pool.apply_async', mock_apply_async_func)
@mock.patch('builtins.open', new_callable=mock.mock_open, read_data=fake_file_info.data)
@mock.patch('os.access')
@mock.patch('os.path.exists')
@mock.patch('os.path.isfile')
@mock.patch('os.path.getsize')
def test_upload(
        mock_path_getsize, mock_path_isfile, mock_path_exists, mock_os_access, mock_open, mock_oarepo):
    test_size = fake_file_info.size
    test_filename = fake_file_info.filename
    mock_os_access.side_effect = lambda fn, mode: fn == test_filename
    mock_path_exists.side_effect = lambda fn: fn == test_filename
    mock_path_isfile.side_effect = lambda fn: fn == test_filename
    mock_path_getsize.side_effect = lambda fn: test_size if fn == test_filename else FileNotFoundError
    token_status_url = f"{mock_oarepo.url}/access-tokens/status"
    record_url = f'{mock_oarepo.url}/draft/records/{mock_oarepo.pid}'
    files_url = f'{record_url}/files/'
    responses.add(responses.GET, token_status_url, status=200,
        json={
            'status': 'OK',
            'links': {
                'files': files_url
            }
        }
    )
    init_url = f"{files_url}?multipart=true"
    responses.add(responses.POST, init_url, status=201,
        json={
            'key': mock_oarepo.s3key,
            'uploadId': mock_oarepo.uploadId
        }
    )
    file_url = f'{files_url}{mock_oarepo.key}'
    upload_url = f'{file_url}/{mock_oarepo.uploadId}'
    presign_url = f"{upload_url}/{mock_oarepo.partNum}/presigned"
    part_s3_url = 'https://mock_part_s3_url.example.org'
    responses.add(responses.GET, presign_url, status=200,
        json={
          'url': part_s3_url,
        }
    )
    responses.add(responses.PUT, part_s3_url, status=201,
        headers={'ETag': mock_oarepo.ETag}
    )
    complete_url = f"{upload_url}/complete"
    responses.add(responses.POST, complete_url, status=200,
        json={
            'location': file_url
        }
    )

    token, url, key = mock_oarepo.token, mock_oarepo.url, mock_oarepo.key
    args = ['-t', token, '-d', '-e', url, 'upload', '-p', '1', '-k', key, '-f', test_filename]
    result = CliRunner(mix_stderr=False).invoke(cli_main, args)
    # result = cli_main(args)
    print(result.output)
    print(result.stderr_bytes)
    print(result.stderr)
    assert result.exit_code == 0
    # assert result.output == ''
    assert re.match(f"^.*\nOK: Finished upload.*\\[https://.*/{key}]\n$", result.output, re.MULTILINE|re.DOTALL)


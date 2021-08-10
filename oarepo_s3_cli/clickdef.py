# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 CESNET
#
# OARepo-S3-CLI is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.

""" OARepo S3 client CLI wrapper. """

import sys
import click
import logging
import urllib3
from oarepo_s3_cli.utils import *
from oarepo_s3_cli.lib import OARepoS3Client
from oarepo_s3_cli.constants import *

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CTX_VARS=['debug', 'quiet', 'endpoint', 'token', 'logger']

@click.group()
@click.pass_context
@click.option('-d', '--debug', default=False, is_flag=True, show_default=True)
@click.option('-q', '--quiet', default=False, is_flag=True, show_default=True)
@click.option('-e', '--endpoint', required=True, help='OARepo HTTPS endpoint e.g. https://repo.example.org')
@click.option('-t', '--token', required=True, help='Token', envvar='TOKEN', show_default=True)
def cli_main(ctx, debug, quiet, endpoint, token):
    ctx.ensure_object(dict)
    loglevel = logging.INFO
    if quiet:
        loglevel = logging.ERROR
    if debug:
        loglevel = logging.DEBUG
    logging.basicConfig(level=loglevel, format='%(message)s')
    logger = logging.getLogger(__name__)
    for k in CTX_VARS:
        ctx.obj[k] = locals()[k]


@cli_main.command('upload')
@click.pass_context
@click.option('-f', '--file', 'files', required=True, multiple=True, help='file(s) for upload, repeatable')
@click.option('-k', '--key', 'keys', multiple=True,
              help='names(s) for uploaded files, repeatable [default: basename of file]')
@click.option('-p', '--parallel', default=0, type=int, show_default=False,
              help='number of parallel upload streams [default: CPU count]')
def cli_upload(ctx, files, keys, parallel):
    try:
        co = ctx.obj
        logger = ctx.obj['logger']
        if len(keys) < len(files): keys += (len(files)-len(keys)) * (None,)
        for ifile, key in zip(enumerate(files), keys):
            i, file = ifile
            if len(files)>1 and i>0: secho("", nl=True)
            logger.debug(f"{funcname()} file:{file}, key={key}")
            oas3 = OARepoS3Client(co['endpoint'], co['token'], parallel, co['quiet'])
            location = oas3.process_click_upload(key, file)
            # location = f"{i}#{file}:{key}"
            if len(files)>1: secho(f"File {file} uploaded. [{location}]", prefix='OK', quiet=co['quiet'])
            else: secho(f"Done. [{location}]", prefix='OK', quiet=co['quiet'])
    except Exception as e:
        msg, code = e.args if len(e.args)>1 else (e.args[0], STATUS_UNKNOWN)
        logger.debug(f"Error [{msg}]")
        if co['debug']:
            raise e
        else:
            err_fatal(msg, code)

@cli_main.command('resume')
@click.pass_context
@click.option('-f', '--file', 'file', required=True, multiple=False, help='file for upload resume')
@click.option('-k', '--key', required=True, help='key returned from upload')
@click.option('-u', '--uploadId', 'uploadId', required=True, help='uploadId returned from upload')
@click.option('-p', '--parallel', default=0, type=int, show_default=False,
              help='number of parallel upload streams [default: CPU count]')
def cli_resume(ctx, file, key, uploadId, parallel):
    try:
        co = ctx.obj
        logger = ctx.obj['logger']
        logger.debug(f"{funcname()} file={file}, key={key}, uploadId={uploadId}")
        oas3 = OARepoS3Client(co['endpoint'], co['token'], parallel, co['quiet'], key=key)
        location = oas3.process_click_resume(key, file, uploadId)
        secho(f"Done. [{location}]", prefix='OK', quiet=co['quiet'])
    except Exception as e:
        msg, code = e.args if len(e.args)>1 else (e.args[0], STATUS_UNKNOWN)
        logger.debug(f"Error [{msg}]")
        if co['debug']:
            raise e
        else:
            err_fatal(msg, code)


@cli_main.command('abort')
@click.pass_context
@click.option('-k', '--key', required=True, help='key returned from upload')
@click.option('-u', '--uploadId', 'uploadId', required=True, help='uploadId returned from upload')
def cli_abort(ctx, key, uploadId):
    try:
        co = ctx.obj
        logger = ctx.obj['logger']
        oas3 = OARepoS3Client(co['endpoint'], co['token'], False, co['quiet'], key=key)
        oas3.set_uploadId(uploadId)
        oas3.abort_upload()
    except Exception as e:
        msg, code = e.args if len(e.args)>1 else (e.args[0], STATUS_UNKNOWN)
        logger.debug(f"Error [{msg}]")
        if co['debug']:
            raise e
        else:
            err_fatal(msg, code)


@cli_main.command('test')
@click.pass_context
def cli_test(ctx):
    try:
        co = ctx.obj
        logger = ctx.obj['logger']
        oas3 = OARepoS3Client(co['endpoint'], co['token'], False, co['quiet'], key='test')
        oas3.logTest()
        logger.debug(f"Error [{ctx.obj}]")
    except Exception as e:
        if co['debug']:
            raise e
        else:
            err_fatal(e)


if __name__ == '__main__':
    cli_main()

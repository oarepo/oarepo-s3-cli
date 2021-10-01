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

CTX_VARS=['debug', 'quiet', 'endpoint', 'token', 'logger', 'noninteractive']

@click.group()
@click.pass_context
@click.option('-d', '--debug', default=False, is_flag=True, show_default=True)
@click.option('-q', '--quiet', default=False, is_flag=True, show_default=True)
@click.option('-n', '--noninteractive', default=False, is_flag=True, show_default=True)
@click.option('-e', '--endpoint', required=True, help='OARepo HTTPS endpoint e.g. https://repo.example.org')
@click.option('-t', '--token', required=True, help='Access token (can be grabbed from env.variable "TOKEN")', envvar='TOKEN', show_default=True)
def cli_main(ctx, debug, quiet, noninteractive, endpoint, token):
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
              help='object key(s)/names(s) for uploaded files in S3, repeatable [default: basename of file]')
@click.option('-p', '--parallel', default=0, type=int, show_default=False,
              help='number of parallel upload streams [default: CPU count]')
def cli_upload(ctx, files, keys, parallel):
    co = ctx.obj
    logger = ctx.obj['logger']
    if len(keys) < len(files): keys += (len(files)-len(keys)) * (None,)
    # loop over multiple files:
    for ifile, key in zip(enumerate(files), keys):
        i, file = ifile
        if len(files)>1 and i>0: secho("", nl=True)
        logger.debug(f"{funcname()} file:{file}, key={key}")
        try:
            oas3 = OARepoS3Client(co['endpoint'], co['token'], parallel, co['quiet'])
            location, code = oas3.process_click_upload(key, file)
        except (FileNotFoundError, PermissionError) as e:
            msg, code = e.args if len(e.args) > 1 else (e.args[0], STATUS_UNKNOWN)
            err_fatal(msg, code)
        except Exception as e:
            msg, code = e.args if len(e.args) > 1 else (e.args[0], STATUS_UNKNOWN)
            logger.debug(f"Error {code} \"{msg}\"[{type(e)}]")
            uploadId = oas3.get_uploadId()
            if co['noninteractive'] or click.confirm(f"\ntry resume upload?"):
                try:
                    oas3 = OARepoS3Client(co['endpoint'], co['token'], parallel, co['quiet'])
                    location, code = oas3.process_click_resume(key, file, uploadId)
                except Exception as e:
                    msg, code = e.args if len(e.args) > 1 else (e.args[0], STATUS_UNKNOWN)
            if code != STATUS_OK:
                _ask_abort(ctx, oas3, file, key, uploadId, co['noninteractive'])
                if co['debug']:
                    raise e
                else:
                    err_fatal(msg, code)
        secho(f"Finished upload key:{key}. [{location}]", prefix='OK', quiet=co['quiet'])
    if len(files)>1: secho(f"Done.", prefix='OK', quiet=co['quiet'])

@cli_main.command('resume')
@click.pass_context
@click.option('-f', '--file', 'file', required=True, multiple=False, help='file for upload resume')
@click.option('-k', '--key', help='object key (name) of uploaded file in S3 [default: basename of file]')
@click.option('-u', '--uploadId', 'uploadId', required=True, help='uploadId returned from upload')
@click.option('-p', '--parallel', default=0, type=int, show_default=False,
              help='number of parallel upload streams [default: CPU count]')
def cli_resume(ctx, file, key, uploadId, parallel):
    try:
        co = ctx.obj
        logger = ctx.obj['logger']
        logger.debug(f"{funcname()} file={file}, key={key}, uploadId={uploadId}")
        oas3 = OARepoS3Client(co['endpoint'], co['token'], parallel, co['quiet'])
        location, code = oas3.process_click_resume(key, file, uploadId)
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
@click.option('-k', '--key', required=True, help='object key in S3 returned from upload')
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


@cli_main.command('revoke')
@click.pass_context
def cli_revoke(ctx):
    try:
        co = ctx.obj
        logger = ctx.obj['logger']
        oas3 = OARepoS3Client(co['endpoint'], co['token'], False, co['quiet'])
        oas3.revoke_token()
    except Exception as e:
        msg, code = e.args if len(e.args)>1 else (e.args[0], STATUS_UNKNOWN)
        logger.debug(f"Error [{msg}]")
        if co['debug']:
            raise e
        else:
            err_fatal(msg, code)


@cli_main.command('check')
@click.pass_context
@click.option('-f', '--file', 'file', required=True, multiple=False, help='uploaded file to check')
@click.option('-k', '--key', help='object key (name) of uploaded file in S3 [default: basename of file]')
def cli_check(ctx, file, key):
    try:
        co = ctx.obj
        logger = ctx.obj['logger']
        oas3 = OARepoS3Client(co['endpoint'], co['token'], False, co['quiet'])
        result, code = oas3.process_click_check(key, file)
    except Exception as e:
        msg, code = e.args if len(e.args)>1 else (e.args[0], STATUS_UNKNOWN)
        logger.debug(f"Error [{msg}]")
        if co['debug']:
            raise e
        else:
            err_fatal(msg, code)


@cli_main.command('debug_test', hidden=True)
@click.pass_context
def cli_debug_test(ctx):
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


def _ask_abort(ctx, oas3, file, key, uploadId, noninteractive):
    co = ctx.obj
    if noninteractive or click.confirm(f"\ncall abort_upload? (resume will not be possible)"):
        oas3.set_uploadId(uploadId)
        oas3.abort_upload()
    else:
        secho(f'abort_upload skipped.\n resume info:')
        secho(f'   -f "{file}" -k "{key}" -u "{uploadId}"')


if __name__ == '__main__':
    cli_main()

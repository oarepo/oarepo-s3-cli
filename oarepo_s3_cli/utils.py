# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 CESNET
#
# OARepo-S3-CLI is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.
""" OARepo S3 client utils. """

import sys
import os.path
import click
import multiprocessing as mp
import signal
from oarepo_s3_cli.constants import *
from ctypes import c_char

def get_file_chunk_size(file_size):
    def getnumchunks(file_size, chunk_size):
        num = int(file_size / chunk_size)
        remain = file_size % chunk_size
        last_size = chunk_size
        if remain:
            last_size = remain
            num += 1
        return num, chunk_size, last_size
    if file_size <= MIN_PART_SIZE:
        return 1, file_size, file_size
    elif file_size <= MAX_PARTS * MIN_PART_SIZE:
        return getnumchunks(file_size, MIN_PART_SIZE)
    elif file_size <= MAX_PARTS * MAX_PART_SIZE:
        return getnumchunks(file_size, MAX_PART_SIZE)
    else:
        raise Exception(f"Unsupported file size (MAX_PARTS and MAX_PART_SIZE exceeded)", STATUS_WRONG_FILE)

def funcname(colon=True):
    frame = sys._getframe(1)
    argv0 = os.path.basename(sys.argv[0])
    scr = os.path.basename(frame.f_code.co_filename)
    return f"{argv0} ({scr}:{frame.f_lineno} @{frame.f_code.co_name}){':' if colon else ''}"

def procname(colon=False):
    return f"{mp.current_process().name}[{mp.current_process().pid}]{':' if colon else ''}"

def secho(msg, fg='green', quiet=False, prefix='', nl=True):
    if quiet: return
    click.secho(f"{prefix}: " if prefix !='' else '', fg=fg, nl=False)
    click.secho(msg, fg=None, nl=nl)


def err_fatal(msg, st=1):
    click.secho(f"ERR: ", fg='red', nl=False)
    click.secho(msg, fg=None)
    sys.exit(st)

def get_signame(_signo):
    # workaround for pyth.<3.8
    SIGS = {signal.SIGINT: 'Interrupt', signal.SIGTERM: 'Terminated', signal.SIGQUIT: 'Quit',
            signal.SIGKILL: 'Killed', signal.SIGALRM: 'Alarm clock'}
    signame = SIGS[_signo] if _signo in SIGS.keys() else 'Other'
    # pyth.>=3.8: signame = signal.strsignal(_signo)
    return signame


def size_fmt(num, suffix='B', sep=' '):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%.0f%s%s%s" % (num, sep, unit, suffix)
        num /= 1024.0
    return "%.0f%s%s%s" % (num, sep, 'Yi', suffix)

class Stats(object):
    def __init__(self, num_parts=10, finished=0):
        self.num_parts = num_parts
        self.pending = num_parts - finished
        self.running = 0
        self.finished = finished
        self.failed = 0
        self.for_terminate = 0

    def decr(self):
        if self.pending > 0:
            self.pending -= 1
        elif self.running > 0:
            self.running -= 1
        else:
            str = f"{self.pending}/{self.running}/{self.finished}/{self.failed}"
            raise Exception(f"Cannot decrementing ({str})", STATUS_GENERAL_ERROR)

    def start(self, i=1):
        self.pending -= i
        self.running += i

    def finish(self):
        self.decr()
        self.finished += 1

    def fail(self):
        self.decr()
        self.failed += 1

    def terminate(self):
        self.decr()
        self.for_terminate += 1

    @property
    def remaining(self):
        return self.num_parts - self.finished - self.failed


class Spinner(object):
    def __init__(self):
        self.chars = '|/-\\'
        self.len = len(self.chars)
        self.index = 0

    def get(self):
        spinchar = self.chars[self.index]
        self.index = self.index + 1 if self.index + 1 < self.len else 0
        return spinchar


class UploadFailedException(Exception):
    pass

class SignalException(Exception):
    pass

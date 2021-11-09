# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 CESNET
#
# OARepo-S3-CLI is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.
""" OARepo S3 client utils. """

import click, hashlib, requests, signal, sys, time
import os.path
import multiprocessing as mp
from oarepo_s3_cli.constants import *

def get_file_chunk_size(file_size):
    def getnumchunks(file_size, chunk_size):
        num = int(file_size / chunk_size)
        remain = file_size % chunk_size
        last_size = chunk_size
        if remain:
            last_size = remain
            num += 1
        return num, chunk_size, last_size
    # return Math.min(Math.max(MIN_PART_SIZE, Math.ceil(file_size / MAX_PARTS)), MAX_PART_SIZE)
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
        self.ts = 0

    def set_ts(self):
        self.ts = time.time()

    def decr(self):
        if self.pending > 0:
            self.pending -= 1
        elif self.running > 0:
            self.running -= 1
        else:
            str = f"{self.pending}/{self.running}/{self.finished}/{self.failed}"
            raise Exception(f"Cannot decrementing ({str})", STATUS_GENERAL_ERROR)
        self.set_ts()

    def start(self, i=1):
        self.pending -= i
        self.running += i
        self.set_ts()

    def finish(self):
        self.decr()
        self.finished += 1
        self.set_ts()

    def fail(self):
        self.decr()
        self.failed += 1
        self.set_ts()

    def terminate(self):
        self.decr()
        self.for_terminate += 1
        self.set_ts()

    @property
    def remaining(self):
        return self.num_parts - self.finished - self.failed

class SharedList():
    def __init__(self, action, unfin, grouplen, maxlen):
        self.action = action
        self.unfin = unfin
        self.grouplen = grouplen
        self.maxlen = maxlen
        mpman = mp.Manager()
        self.list = mpman.dict()
        self.idx = 0

    def prepare(self, cnt=0):
        if cnt==0: cnt = self.maxlen
        # cutting to smaller groups:
        if cnt>self.grouplen:
            for x in range(cnt // self.grouplen + (1 if (cnt % self.grouplen)>0 else 0)):
                self.prepare(self.grouplen)
            return
        pnums = []
        groupmax = min(self.idx+cnt, len(self.unfin))
        if groupmax > self.idx:
            for i in range(self.idx, groupmax):
                pn = self.unfin[i]
                pnums.append(pn)
            vals = self.action(pnums)
#            secho(f"\npresigns.prepare: {pnums} ({len(self.list)}/{self.maxlen})")
            for pn in vals:
                self.list[pn] = vals[pn]
            self.idx = groupmax
            # logger.debug(f" feeding list by {','.join(map(str,pnums))} idx={self.idx}")

    def supply(self, cnt=0, min=0):
        if min==0: min=self.grouplen
        if len(self.list) < min:
            self.prepare(cnt)

    def iter(self):
        return(self.list)

    def has_key(self, pn):
        return(pn in self.list)

    def pop(self, pn):
        return(self.list.pop(pn, None))

    def get_value(self, pn):
        return(self.list[pn])

class Spinner(object):
    def __init__(self):
        self.chars = '|/-\\'
        self.len = len(self.chars)
        self.index = 0

    def get(self):
        spinchar = self.chars[self.index]
        self.index = self.index + 1 if self.index + 1 < self.len else 0
        return spinchar

def get_local_hash(file, _part_size=0):
    hashes = []
    part_size = _part_size if _part_size!=0 else MIN_PART_SIZE
    with open(file, "rb") as f:
        while 1:
            chunk = f.read(part_size)
            if not chunk: break
            hashes.append(hashlib.md5(chunk).digest())
    local_hash = hashlib.md5(b''.join(hashes)).hexdigest() + '-' + str(len(hashes))
    return local_hash

def get_remote_hash(token, url, _part_size=0):
    hashes = []
    part_size = _part_size if _part_size!=0 else MIN_PART_SIZE
    headers = {
        'Authorization': f"Bearer {token}"
    }
    resp = requests.get(url, stream=True, headers=headers, verify=False)
    if resp.status_code >= 400:
        raise Exception(f"Can't read remote file.", STATUS_GENERAL_ERROR)
    for chunk in resp.iter_content(part_size):
        hashes.append(hashlib.md5(chunk).digest())
    remote_hash = hashlib.md5(b''.join(hashes)).hexdigest() + '-' + str(len(hashes))
    return remote_hash


class UploadFailedException(Exception):
    pass

class SignalException(Exception):
    pass

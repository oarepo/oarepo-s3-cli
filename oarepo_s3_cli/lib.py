# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 CESNET
#
# OARepo-S3-CLI is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.

""" OARepo S3 client lib. """

import hashlib, re
from os import path
import time, requests, json, logging
from urllib3.exceptions import NewConnectionError
import multiprocessing as mp

from oarepo_s3_cli.utils import *
from oarepo_s3_cli.constants import *
from oarepo_s3_cli.parallels import Parallels

# logging.basicConfig(level=logging.DEBUG)
# logger = logging.getLogger(__name__)
logger = logging
# logger.addHandler(logging.NullHandler())
# logger.setLevel(logging.INFO)
# ch = logging.StreamHandler()
# logger.addHandler(ch)
# urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class OARepoS3Client(object):
    """ """
    def __init__(self, url, token, parallel=1, quiet=False, key=None):
        self.url = url
        # don't use certificates on localhost:
        self.https_verify = not re.match(f"^https://127\\.0\\.0\\.1:", url)
        self.token = token
        self.parallel = MAX_PARALLEL if parallel == 0 else parallel
        self.quiet = quiet
        self.key = key
        self.contentType = 'application/octet-stream'
        self.parts, self.parts_unfin, self.uploadId, self.output = [], [], None, ''
        self.urlFiles = self.check_token_status(self.token)

    def process_click_upload(self, key=None, file=None):
        self.set_file(file, key)
        self.init_upload()
        return self.do_upload()

    def process_click_resume(self, key, file, uploadId):
        self.set_file(file, key)
        self.set_uploadId(uploadId)
        # parts = self.get_parts()
        self.scan_parts()
        logger.debug(f"{funcname()} parts:\n{self.parts}")
        logger.debug(f"{funcname()} results:\n{self.results}")
        # parts = json.loads(parts)
        # secho(f"parts: \n{parts}", prefix='OK', quiet=self.quiet)
        secho(f"{len(self.parts)} part(s) already uploaded.", prefix='OK', quiet=self.quiet)
        return self.do_upload()

    def do_upload(self):
        for partNum in range(1, self.num_parts+1):
            if self.results[partNum-1] is None:
                self.parts_unfin.append(partNum)
        logger.debug(f"{funcname()} parts_unfin:\n{self.parts_unfin}")
        try:
            # parts_unfin = range(1, self.num_parts + 1)
            st = STATUS_OK
            if len(self.parts_unfin) > 0:
                self.parallels = Parallels(
                    self.upload_part, self.num_parts, self.parts_unfin, parallel=self.parallel, quiet=self.quiet
                )
                st, newparts = self.parallels.main()
                self.parts += newparts
            if st == STATUS_OK:
                logger.debug(f"{funcname()} parts:\n{self.parts}")
                location = self.complete_upload()
                return location, STATUS_OK
            else:
                raise Exception(f"Upload failed with status {st}.", st)
        except Exception as e:
            logger.debug(f"{funcname()} caught and raising Exception \"{e}\" {procname()}")
            raise e

    def process_click_check(self, key, file):
        self.set_file(file, key, showInfo=False)
        msg = f"Checking file uploaded as key {self.key} with local file {file} ..."
        secho(f"{msg}", quiet=self.quiet)
        urlFile = f"{self.urlFiles}{self.key}"
        pool = mp.Pool(1)
        fut_rem = pool.apply_async(get_remote_hash, args=(self.token, urlFile,))
        pool.close()

        local_hash = get_local_hash(file)
        logger.debug(f"\n local blake2b hash: {local_hash}")

        remote_hash = fut_rem.get()
        pool.join()
        # remote_hash = get_remote_hash(self.token, urlFile)

        logger.debug(f"\n remote blake2b hash: {remote_hash}")
        if local_hash==remote_hash:
            secho(f"Local and remote files have the same blake2b hash.",
                prefix='OK', quiet=self.quiet)
            return True, STATUS_OK
        # return False, STATUS_GENERAL_ERROR
        raise Exception(f"Local and remote files differ.", STATUS_GENERAL_ERROR)

    def check_token_status(self, token):
        token_status_url = f"{self.url}/access-tokens/status"
        headers = { 'Authorization': f"Bearer {token}" }
        resp = requests.get(token_status_url, headers=headers, verify=self.https_verify)
        if resp.status_code != 200:
            raise PermissionError(f"Invalid token (http code {resp.status_code})", STATUS_INVALID_TOKEN)
        resp_json = resp.json()
        if resp_json['status'] != 'OK':
            raise PermissionError(f"Expired token", STATUS_EXPIRED_TOKEN)
        return resp_json['links']['files']

    def set_uploadId(self, uploadId):
        self.uploadId = uploadId
        self.urlUpload = f"{self.urlFiles}{self.key}/{self.uploadId}"


    def get_uploadId(self):
        return self.uploadId


    def set_file(self, file=None, key=None, showInfo=True):
        if file is None or not path.exists(file) or not path.isfile(file):
            raise FileNotFoundError(f"File not found ({file})", STATUS_WRONG_FILE)
        if not os.access(file, os.R_OK):
            raise PermissionError(f"File not readable ({file})", STATUS_WRONG_FILE)
        self.file = file
        self.key = key if not (key is None or key=='') else path.basename(file)
        self.data_size = path.getsize(file)
        self.num_parts, self.part_size, self.last_size = get_file_chunk_size(self.data_size)
        self.results = [None for i in range(self.num_parts)]
        if showInfo:
            msg = f"Uploading file {file} {'' if self.key=='' else f'as key {self.key}'}\n" \
                f"    in {self.num_parts} part(s)" \
                f" using up to {self.parallel} parallel stream(s)," \
                f" part size: {self.part_size}, last part size: {self.last_size} ..."
            secho(f"{msg}", quiet=self.quiet)

    def scan_parts(self):
        try:
            parts = self.get_parts()
            self.parts = [{"ETag": part["ETag"], "PartNumber": part["PartNumber"]} for part in parts]
            for part in self.parts:
                self.results[part["PartNumber"] - 1] = {"ETag": part["ETag"], "PartNumber": part["PartNumber"]}
        except:
            raise

    def init_upload(self):
        logger.debug(f"{funcname()} init_upload")
        init_url = f"{self.urlFiles}?multipart=true"
        fileinfo = {
            'key': self.key,
            'name': self.key,
            'multipart_content_type': self.contentType,
            'size': self.data_size,
        }
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {self.token}"
        }
        logger.debug(f"{funcname()} {init_url}")
        logger.debug(f"{funcname()} {fileinfo}")
        logger.debug(f"{funcname()} {headers}")
        resp = requests.post(init_url, data=json.dumps(fileinfo), headers=headers, verify=self.https_verify)
        logger.debug(f"{funcname()} status: {resp.status_code}")
        if resp.status_code != 201:
            raise Exception(f"{funcname()} failed (http code {resp.status_code})", STATUS_WRONG_SERVER_RESPONSE)
        resp_json = resp.json()
        s3key, uploadId = resp_json['key'], resp_json['uploadId']
        self.set_uploadId(uploadId)
        secho(f"Upload initialized (uploadId {uploadId})", prefix='OK', quiet=self.quiet)
        logger.debug(f"{funcname()} uploadId: {uploadId}, s3key: {s3key}")
        return uploadId


    def presign_part_upload(self, partNum):
        presign_url = f"{self.urlUpload}/{partNum}/presigned"
        logger.debug(f"{funcname()} presign_part_upload (url:{presign_url})")
        try:
            resp = requests.get(presign_url, verify=self.https_verify)
            logger.debug(f"{funcname()} status: {resp.status_code}")
            if resp.status_code >= 400:
                raise Exception(f"Upload presign failed. (http code {resp.status_code})")
            logger.debug(f"{funcname()} status: {resp.json()}")
            resp_json = resp.json()
            part_s3_url = resp_json['url'] if 'url' in resp_json.keys() else resp_json['presignedUrls'][str(partNum)]
            logger.debug(f"{funcname()} part_s3_url: {part_s3_url}")
            return part_s3_url
        except Exception as e:
            logger.debug(f"{funcname()} #{partNum} caught and raising Exception \"{e}\" {procname()}")
            raise type(e)(e.args).with_traceback(sys.exc_info()[2])


    def get_parts(self):
        parts_url = f"{self.urlUpload}/parts"
        logger.debug(f"{funcname()} parts_url:{parts_url}")
        resp = requests.get(parts_url, verify=self.https_verify)
        if resp.status_code >= 400:
            raise Exception(f"Upload not found. (http code {resp.status_code})")
        logger.debug(f"{funcname()} status:{resp.status_code} resp.text: {resp.text}")
        return resp.json()


    def complete_upload(self):
        complete_url = f"{self.urlUpload}/complete"
        logger.debug(f"{funcname()} complete_upload (url: {complete_url})")
        parts4complete = {"parts": []}
        for part in self.parts:
            if part is not None:
                parts4complete['parts'].append({
                    'ETag': part['ETag'],
                    'PartNumber': part['PartNumber']
                })
        parts4complete_json = json.dumps(parts4complete)
        # logger.debug(f"{funcname()} parts: {parts4complete}")
        logger.debug(f"{funcname()} parts_json: {parts4complete_json}")
        headers = {'Content-Type': 'application/json'}
        secho('Completing upload ...', quiet=self.quiet)
        resp = requests.post(complete_url, data=parts4complete_json, headers=headers, verify=self.https_verify)
        logger.debug(f"{funcname()} status: {resp.status_code}")
        # logger.debug(f"{funcname()} resp.text: {resp.text}")
        if resp.status_code >= 400:
            raise Exception(f"Upload completing failed (http code {resp.status_code})", STATUS_WRONG_SERVER_RESPONSE)
        location = resp.json()['location']
        logger.debug(f"{funcname()} location: {location}")
        secho(f'Upload completed. ({location})', prefix='OK', quiet=self.quiet)
        return location


    def abort_upload(self):
        abort_url = f"{self.urlUpload}/abort"
        logger.debug(f"{funcname()} abort_url:{abort_url}")
        secho('Aborting upload ...', quiet=self.quiet)
        resp = requests.delete(abort_url, verify=self.https_verify)
        if resp.status_code >= 400:
            raise Exception(f"Upload abort failed (http code {resp.status_code})", STATUS_WRONG_SERVER_RESPONSE)
        logger.debug(f"{funcname()} status:{resp.status_code} resp.text: {resp.text}")
        secho(f'Upload aborted.', prefix='OK', quiet=self.quiet)
        return resp


    def revoke_token(self):
        revoke_url = f"{self.url}/access-tokens/revoke"
        logger.debug(f"{funcname()} revoke_url:{revoke_url}")
        secho('Revoking token ...', quiet=self.quiet)
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {self.token}"
        }
        resp = requests.post(revoke_url, headers=headers, verify=self.https_verify)
        if resp.status_code >= 400:
            raise Exception(f"Token revoke failed (http code {resp.status_code})", STATUS_WRONG_SERVER_RESPONSE)
        logger.debug(f"{funcname()} status:{resp.status_code} resp.text: {resp.text}")
        secho(f'Token revoked.', prefix='OK', quiet=self.quiet)
        return resp


    def delete_file(self):
        logger.debug(f"{funcname()} delete_file")
        delete_url = f"{self.urlFiles}/{self.key}"
        resp = requests.delete(delete_url, verify=self.https_verify)
        logger.debug(f"{funcname()} status: {resp.status_code}")


    def upload_part(self, partNum, val):
        logger.debug(f"\n>>Starting upload_part #{partNum} ...")
        offset = (partNum-1) * self.part_size
        part_size = self.part_size if partNum < self.num_parts else self.last_size
        part_s3_url = self.presign_part_upload(partNum)
        ok = False
        # raise Exception('EXCEPTION')
        for retry in range(1, MAX_RETRIES + 1):
            if retry>1:
                msg = f' ... #{partNum} trying again ({retry} of {MAX_RETRIES})...'
                secho(f"{msg}", prefix='\nWARN', fg='yellow', quiet=self.quiet)
                time.sleep(RETRY_SLEEP * retry)
            try:
                retry_str = f' retry {retry}' if retry>1 else ''
                logger.debug(f"\n..Opening file {self.file} at offset {offset}{retry_str} ...")
                with open(self.file, 'rb') as fh:
                    fh.seek(offset)
                    data = fh.read(part_size)
                    ETag = None
                    if data is None or len(data)==0:
                        continue
                    logger.debug(f"...#{partNum} PUT upload offset {offset}{retry_str}")
                    # --- request: ---
                    resp = requests.put(part_s3_url, data=data, timeout=3600)
                    logger.debug(f"...#{partNum} resp status:{resp.status_code} headers:{resp.headers}")
                    if 'Connection' in resp.headers and resp.headers['Connection']=='close':
                        continue
                    # logger.debug(f"  #{partNum} resp.text: {resp.text}")
                    ETag = resp.headers['ETag'].strip('"')
                    logger.debug(f"...#{partNum} ETag: {ETag}")
                    ok = True
                    break
            except (NewConnectionError, ConnectionError, socket.gaierror) as e:
                msg = f"Error uploading part #{partNum} retry {retry} from {MAX_RETRIES}"
                secho(f"{msg}", prefix='\nWARN', fg='yellow', quiet=self.quiet)
                logger.debug(f"  #{partNum} Error [{e}]")
            except FileNotFoundError or PermissionError as e:
                msg = f"Error reading file #{self.file} retry {retry} from {MAX_RETRIES}"
                secho(f"{msg}", prefix='\nWARN', fg='yellow', quiet=self.quiet)
                logger.debug(f"  #{partNum} Error [{e}]")
            except SignalException as e:
                emsg, signumber = e.args[1] if len(e.args) > 1 else (None, None)
                msg = f"SIGNAL: Error uploading part #{partNum} retry {retry} from {MAX_RETRIES} [{e}/{type(e)}]"
                # secho(f"{msg}", prefix='\nWARN', fg='yellow', quiet=self.quiet)
                logger.debug(f"  #{partNum} Error [{e}/{type(e)}]")
                if signumber != signal.SIGALRM: break
            except Exception as e:
                msg = f"General error uploading part #{partNum} retry {retry} from {MAX_RETRIES} [{e}/{type(e)}]"
                secho(f"{msg}", prefix='\nWARN', fg='yellow', quiet=self.quiet)
                logger.debug(f"  #{partNum} Error [{e}/type(e)]")

        logger.debug(f"<<<Stop upload_part #{partNum} status:{'OK' if ok else 'ERR'}.")
        if ok:
            return dict(PartNumber=partNum, status=STATUS_OK, ETag=ETag)
        else:
            raise Exception(f"Part {partNum} upload failed.", STATUS_ERR_MAX_RETRIES)


    def logTest(self):
        logger.debug(f"debug")
        logger.info(f"info")
        logger.warning(f"warning")
        logger.critical(f"critical")
        logger.error(f"error")
        secho(f'Test quiet:{self.quiet}', prefix='test', fg='blue', quiet=self.quiet)


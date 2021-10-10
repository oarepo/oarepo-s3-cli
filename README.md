# oarepo-s3-cli

[![][license_badge]][license]
[![][status_badge]][actions]
[![][pypi_badge]][pypi_url]

---
OARepo command-line upload client

## global options
 * -e, --endpoint `<url>` OARepo HTTPS endpoint e.g. https://repo.example.org (required)
 * -t, --token `<string>` upload auth token obtained from OARepo (required, can be alternatively specified in env.variable "TOKEN")
 * -d, debug (default: False)
 * -q, quiet (default: False)
 * -n, --noninteractive (default: False)
 * --help

## commands
  * upload ... upload file
  * resume ... resume interrupted upload
  * abort ... abort upload
  * check ... match sha256sum of local and uploaded file
  * revoke ... revoke supplied access token

### *upload* command options
   * -f, --file `<filepath>` file(s) for upload (repeatable, required)
   * -k, --key `<name>` object key in S3 (default: basename of file)
   * -p, --parallel `<integer>` (default: CPU count)

### *resume* command options
   * -k, --key `<name>` object key in S3 (default: basename of file)
   * -u, --uploadId `<string>` uploadId returned from upload  (required)
   * -f, --file `<filepath>` file for upload (required)
   * -p, --parallel `<integer>` number of parallel upload streams (default: CPU count)

### *abort* command options
   * -k, --key `<name>` object key in S3 (default: basename of file)
   * -u, --uploadId `<string>` uploadId returned from upload  (required)

### *check* command options
   * -f, --file `<filepath>` uploaded file for check (required)
   * -k, --key `<name>` object key of uploaded file in S3 (default: basename of file)

### *revoke* command options
   none

  [license_badge]: https://img.shields.io/github/license/oarepo/oarepo-s3-cli.svg "license badge"
  [license]: https://github.com/oarepo/oarepo-s3-cli/blob/master/LICENSE "license text"
  [status_badge]: https://github.com/oarepo/oarepo-s3-cli/actions/workflows/main.yml/badge.svg "status badge"
  [actions]: https://github.com/oarepo/oarepo-s3-cli/actions/ "actions"
  [pypi_badge]: https://img.shields.io/pypi/v/oarepo-s3-cli.svg "pypi badge"
  [pypi_url]: https://pypi.org/pypi/oarepo-s3-cli "pypi url"

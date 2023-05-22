#!/usr/bin/env bash

set -e

cd "$(dirname "$0")/.."

python3 -m pip install --requirement requirements.txt

git config --global --fixed-value --replace-all safe.directory "${PWD}" "${PWD}"

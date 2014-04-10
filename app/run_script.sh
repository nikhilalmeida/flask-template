#!/bin/bash
[ $VIRTUALENV ] || VIRTUALENV=venv
source ${VIRTUALENV}/bin/activate >/dev/null

PYTHONPATH="./:dt:es:$PYTHONPATH"
export PYTHONPATH >/dev/null

python "$@"


#!/bin/bash

# Refuse execution unless sourced.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    echo "Error: This script must be sourced, not executed." >&2
    echo "Usage: source ${BASH_SOURCE[0]}" >&2
    exit 1
fi

eval "$(ssh-agent -s)"
ssh-add ~/.ssh/devcybiko_github
ssh -T git@github.com -i ~/.ssh/devcybiko_github

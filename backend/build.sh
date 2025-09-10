#!/usr/bin/env bash
# exit on error
set -o errexit

# Upgrade the build tools
pip install --upgrade pip setuptools wheel

# Install the dependencies from requirements.txt
pip install --no-cache-dir -r requirements.txt
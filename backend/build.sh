#!/usr/bin/env bash
# exit on error
set -o errexit

echo "--- Upgrading build tools ---"
pip install --upgrade pip setuptools wheel

echo "--- Forcefully uninstalling google-generativeai to ensure a clean slate ---"
pip uninstall -y google-generativeai || echo "google-generativeai not found, continuing..."

echo "--- Installing dependencies from requirements.txt ---"
pip install --no-cache-dir -r requirements.txt

echo "--- Verifying installed packages ---"
pip list

echo "--- Checking specific version of google-generativeai ---"
pip show google-generativeai
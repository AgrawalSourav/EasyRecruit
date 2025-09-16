#!/usr/bin/env bash
# exit on error
set -o errexit

echo "--- Upgrading build tools ---"
pip install --upgrade pip setuptools wheel

echo "--- Forcefully uninstalling google-generativeai to ensure a clean slate ---"
pip uninstall -y google-generativeai || echo "google-generativeai not found, continuing..."

echo "--- Installing dependencies from requirements.txt ---"
pip install --no-cache-dir -r requirements.txt

# --- ADD THIS SECTION TO PRE-DOWNLOAD THE SENTENCE TRANSFORMER MODEL ---
echo "--- Pre-downloading Sentence Transformer model ---"
# Create a temporary Python script to run the download
cat << EOF > download_model.py
from sentence_transformers import SentenceTransformer
print("Downloading and caching model 'all-mpnet-base-v2'...")
SentenceTransformer('all-mpnet-base-v2')
print("Model download complete.")
EOF
# Run the script
python download_model.py
echo "--- Model caching complete ---"
# --- END OF NEW SECTION ---

echo "--- Verifying installed packages ---"
pip list

echo "--- Checking specific version of google-generativeai ---"
pip show google-generativeai
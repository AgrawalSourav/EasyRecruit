# debug_app.py
# PURPOSE: A minimal app to test if Render can respond with CORS headers at all.
from flask import Flask, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)

# Use the most permissive CORS setting possible for this test.
# This allows requests from ANY origin.
CORS(app, supports_credentials=True, origins="*") 

@app.route('/')
def health_check():
    """A simple health check endpoint."""
    return jsonify({"status": "ok", "message": "Debug app is running!"})

@app.route('/test-cors')
def test_cors():
    """A specific endpoint to test CORS response."""
    return jsonify({"message": "CORS test successful!"})

# This part is ONLY needed if you are NOT using a Gunicorn start command.
# If using Gunicorn, this block does nothing.
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
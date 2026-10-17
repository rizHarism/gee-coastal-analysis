from http.server import BaseHTTPRequestHandler
import sys
import os

# Pastikan folder api/ berada dalam sys.path
api_dir = os.path.dirname(os.path.abspath(__file__))
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

try:
    from get_cvi import handler
except ImportError:
    from api.get_cvi import handler

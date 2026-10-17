from http.server import BaseHTTPRequestHandler
import sys
import os

api_dir = os.path.dirname(os.path.abspath(__file__))
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

try:
    from get_cvi import handler as gee_handler
except ImportError:
    from api.get_cvi import handler as gee_handler

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Tangani request API
        if self.path.startswith('/api/'):
            return gee_handler.do_GET(self)
        
        # Jika bukan /api/, kembalikan 404 agar tidak merender JSON secara tak sengaja
        self.send_response(404)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"error": "Endpoint not found"}')
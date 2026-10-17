from http.server import BaseHTTPRequestHandler
import sys
import os
import mimetypes

# Pastikan folder api/ berada dalam sys.path
api_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(api_dir)
public_dir = os.path.join(root_dir, 'public')

if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

try:
    from get_cvi import handler as gee_handler
except ImportError:
    from api.get_cvi import handler as gee_handler

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        clean_path = self.path.split('?')[0].rstrip('/')
        
        # 1. Jalur API GEE
        if self.path.startswith('/api/'):
            return gee_handler.do_GET(self)
        
        # 2. Jalur Halaman Statis Frontend
        target_file = None
        if clean_path in ('', '/'):
            target_file = os.path.join(public_dir, 'index.html')
        elif clean_path == '/cesium':
            target_file = os.path.join(public_dir, 'cesium.html')
        elif clean_path == '/leaflet':
            target_file = os.path.join(public_dir, 'leaflet.html')
        else:
            relative_file = clean_path.lstrip('/')
            potential_path = os.path.join(public_dir, relative_file)
            if os.path.exists(potential_path) and os.path.isfile(potential_path):
                target_file = potential_path

        if target_file and os.path.exists(target_file):
            try:
                mime_type, _ = mimetypes.guess_type(target_file)
                if not mime_type:
                    mime_type = 'text/html' if target_file.endswith('.html') else 'application/octet-stream'
                
                with open(target_file, 'rb') as f:
                    content = f.read()

                self.send_response(200)
                self.send_header('Content-type', f'{mime_type}; charset=utf-8')
                self.send_header('Content-length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"Gagal membaca file statis: {str(e)}".encode())
                return
        
        # Fallback jika rute tidak dikenali
        return gee_handler.do_GET(self)

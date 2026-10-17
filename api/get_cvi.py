from http.server import BaseHTTPRequestHandler
import json
import os
from urllib.parse import urlparse, parse_qs
import ee
from dotenv import load_dotenv
import traceback
import datetime

load_dotenv()

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. Ambil Kunci GEE dari Environment Variable
        ee_key_json = os.environ.get('GEE_SERVICE_ACCOUNT_KEY')
        
        if not ee_key_json:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "GEE_SERVICE_ACCOUNT_KEY tidak ditemukan di environment."}).encode())
            return

        # 2. Otentikasi ke Google Earth Engine
        try:
            key_data = json.loads(ee_key_json)
            credentials = ee.ServiceAccountCredentials(key_data['client_email'], key_data=ee_key_json)
            ee.Initialize(credentials=credentials, project=key_data['project_id'])
        except Exception as e:
            print("--- GEE Initialization Error Traceback ---")
            traceback.print_exc() 
            print("------------------------------------------")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Gagal Inisialisasi GEE: {str(e)}"}).encode())
            return

        # 3. Tangkap Parameter Dinamis dari Frontend (URL Query)
        parsed_path = urlparse(self.path)
        params = parse_qs(parsed_path.query)
        
        current_year = datetime.date.today().year
        year_param = params.get('year', [str(current_year)])[0]

        try:
            year = int(year_param)
            if year < 2016 or year > current_year:
                raise ValueError(f"Tahun harus berada dalam rentang 2016 hingga {current_year}")
        except ValueError as err:
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Parameter tahun tidak valid: {str(err)}"}).encode())
            return

        # Hitung rentang tanggal dinamis
        start_date = f"{year}-01-01"
        if year == current_year:
            end_date = datetime.date.today().isoformat()
        else:
            end_date = f"{year}-12-31"

        # 4. Pemrosesan Data GEE (Pekalongan AOI)
        try:
            roi = ee.FeatureCollection('projects/original-folio-510209-p7/assets/AOI-pekalongan')
            
            # Ambil citra Sentinel-2 secara dinamis berdasarkan input tahun
            s2 = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                  .filterBounds(roi)
                  .filterDate(start_date, end_date)
                  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
                  .median()
                  .clip(roi))
            
            # 1. Citra RGB (True Color)
            rgb = s2.select(['B4', 'B3', 'B2'])
            url_rgb = rgb.getMapId({'min': 0, 'max': 3000})['tile_fetcher'].url_format

            # 2. MNDWI (Modified Normalized Difference Water Index) -> (Green - SWIR1) / (Green + SWIR1)
            mndwi = s2.normalizedDifference(['B3', 'B11']).clip(roi)
            url_mndwi = mndwi.getMapId({
                'min': -0.5,
                'max': 0.5,
                'palette': ['#ece7f2', '#a6bddb', '#02818a', '#014636']
            })['tile_fetcher'].url_format

            # 3. NDVI (Hanya Vegetasi > 0.2, selain vegetasi dibuat transparan)
            ndvi = s2.normalizedDifference(['B8', 'B4'])
            ndvi_masked = ndvi.updateMask(ndvi.gt(0.2)).clip(roi)
            url_ndvi = ndvi_masked.getMapId({
                'min': 0.2,
                'max': 0.8,
                'palette': ['#d9f0a3', '#78c679', '#238443', '#004529']
            })['tile_fetcher'].url_format

            # 5. Kirim Respons Balik ke Frontend
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response_data = {
                'year': year,
                'date_range': {
                    'start': start_date,
                    'end': end_date
                },
                'tiles': {
                    'rgb': url_rgb,
                    'mndwi': url_mndwi,
                    'ndvi': url_ndvi
                }
            }
            self.wfile.write(json.dumps(response_data).encode())

        except Exception as e:
            traceback.print_exc()
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Gagal memproses data GEE: {str(e)}"}).encode())

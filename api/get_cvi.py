from http.server import BaseHTTPRequestHandler
import json
import os
from urllib.parse import urlparse, parse_qs
import ee
from dotenv import load_dotenv
import traceback

load_dotenv()

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. Ambil Kunci GEE dari Environment Variable
        ee_key_json = os.environ.get('GEE_SERVICE_ACCOUNT_KEY')
        
        if not ee_key_json:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"Error: GEE_SERVICE_ACCOUNT_KEY tidak ditemukan di environment.")
            return

        # 2. Otentikasi ke Google Earth Engine
        try:
            key_data = json.loads(ee_key_json)
            credentials = ee.ServiceAccountCredentials(key_data['client_email'], key_data=ee_key_json)
            ee.Initialize(credentials=credentials, project=key_data['project_id'])
        except Exception as e:
            # 1. Print the traceback directly to your server console/terminal
            print("--- GEE Initialization Error Traceback ---")
            traceback.print_exc() 
            print("------------------------------------------")
            self.send_response(traceback.print_exc())
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Gagal Inisialisasi GEE: {str(e)}".encode())
            return

        # 3. Tangkap Parameter Dinamis dari Frontend (URL Query)
        parsed_path = urlparse(self.path)
        params = parse_qs(parsed_path.query)
        
        # Nilai default jika frontend tidak mengirimkan parameter
        start_date = params.get('start', ['2025-01-01'])[0]
        end_date = params.get('end', ['2026-03-01'])[0]
        palette_param = params.get('palette', [''])[0]

        # Jika kosong atau tidak dikirim, gunakan warna standar mitigasi bencana
        if not palette_param or palette_param.strip() == "":
            palette_choice = ['#31a354', '#fec44f', '#de2d26']
        else:
            palette_choice = palette_param.split(',')
        palette_choice = params.get('palette', ['#31a354,#fec44f,#de2d26'])[0].split(',')

        # 4. Pemrosesan Data GEE (Pekalongan)
        try:
            roi = ee.FeatureCollection('projects/original-folio-510209-p7/assets/AOI-pekalongan')
            
            # Ambil citra Sentinel-2 secara dinamis berdasarkan input tanggal
            s2 = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                  .filterBounds(roi)
                  .filterDate(start_date, end_date)
                  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
                  .median()
                  .clip(roi))
            
            # Hitung Parameter 1: Vegetasi (NDVI)
            ndvi = s2.normalizedDifference(['B8', 'B4'])
            
            # Hitung Parameter 2: Kemiringan Lereng dari Copernicus DEM
            demCollection = ee.ImageCollection('COPERNICUS/DEM/GLO30_2024_1');
            nativeProj = demCollection.first().projection();
            dataset = demCollection.mosaic().setDefaultProjection(nativeProj);
            dem = dataset.select('DEM');
            slope = ee.Terrain.slope(dem).clip(roi)
            
            # Simulasi Skor CVI Sederhana
            score_slope = ee.Image(1).where(slope.lte(1), 3).where(slope.gt(1).And(slope.lte(3)), 2).where(slope.gt(3), 1)
            score_veg = ee.Image(1).where(ndvi.lte(0.1), 3).where(ndvi.gt(0.1).And(ndvi.lte(0.4)), 2).where(ndvi.gt(0.4), 1)
            cvi_sederhana = score_slope.add(score_veg)
            
            # Dapatkan Tile URL resmi dari GEE menggunakan Palet Dinamis
            # Dapatkan Tile URL untuk masing-masing parameter
            url_cvi = cvi_sederhana.clip(roi).getMapId({'min': 2, 'max': 6, 'palette': palette_choice})['tile_fetcher'].url_format
            url_ndvi = ndvi.clip(roi).getMapId({'min': 0, 'max': 0.8, 'palette': ['blue', 'white', 'green']})['tile_fetcher'].url_format
            url_slope = slope.clip(roi).getMapId({'min': 0, 'max': 5, 'palette': ['green', 'yellow', 'red']})['tile_fetcher'].url_format

            # 5. Kirim Respons Balik ke Frontend
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*') # Izinkan CORS jika diperlukan
            self.end_headers()
            
            response_data = {
                'cvi': url_cvi,
                'ndvi': url_ndvi,
                'slope': url_slope
            }
            self.wfile.write(json.dumps(response_data).encode())

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Gagal memproses data GEE: {str(e)}".encode())

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import earthaccess
import xarray as xr
import numpy as np
from datetime import datetime
import pandas as pd
import json
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": False
    }
})

# Crear directorio de cache
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# Login a NASA
os.environ["NETRC"] = "/workspaces/sp/_netrc"
auth = earthaccess.login()

def get_cache_key(lat, lon, month, day, hour):
    """Genera clave única para cache"""
    return hashlib.md5(f"{lat}_{lon}_{month}_{day}_{hour}".encode()).hexdigest()

def load_from_cache(cache_key):
    """Carga datos del cache si existen"""
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
                print("✅ Datos cargados desde cache")
                return data
        except:
            return None
    return None

def save_to_cache(cache_key, data):
    """Guarda datos en cache"""
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    with open(cache_file, 'w') as f:
        json.dump(data, f)

def process_year(year, month, day, target_hour, lat, lon, bbox):
    """Procesa un año específico y retorna los datos"""
    year_data = {
        'temps': [],
        'precip': [],
        'wind': [],
        'humidity': []
    }
    
    try:
        historical_date = f"{year}-{month:02d}-{day:02d}"
        
        # DATASET 1: M2T1NXSLV
        search_slv = earthaccess.search_data(
            short_name='M2T1NXSLV',
            cloud_hosted=True,
            bounding_box=bbox,
            temporal=(historical_date, historical_date),
        )
        
        # DATASET 2: M2T1NXFLX
        search_flx = earthaccess.search_data(
            short_name='M2T1NXFLX',
            cloud_hosted=True,
            bounding_box=bbox,
            temporal=(historical_date, historical_date),
        )
        
        # Procesar SLV (temperatura, viento, humedad)
        if len(search_slv) > 0:
            files_slv = earthaccess.open(search_slv)
            
            for file in files_slv:
                try:
                    ds = xr.open_dataset(file, engine='h5netcdf')
                    
                    if 'time' in ds.dims and len(ds.time) > 1:
                        hours = [pd.to_datetime(t).hour for t in ds.time.values]
                        closest_idx = min(range(len(hours)), key=lambda i: abs(hours[i] - target_hour))
                        ds = ds.isel(time=closest_idx)
                    
                    if 'T2M' in ds:
                        temp_array = ds['T2M'].sel(lat=lat, lon=lon, method='nearest').values
                        temp = float(np.mean(temp_array)) - 273.15
                        year_data['temps'].append(temp)
                    
                    if 'U10M' in ds and 'V10M' in ds:
                        u_array = ds['U10M'].sel(lat=lat, lon=lon, method='nearest').values
                        v_array = ds['V10M'].sel(lat=lat, lon=lon, method='nearest').values
                        u = float(np.mean(u_array))
                        v = float(np.mean(v_array))
                        wind = np.sqrt(u**2 + v**2)
                        year_data['wind'].append(wind)
                    
                    if 'RH2M' in ds:
                        humidity_array = ds['RH2M'].sel(lat=lat, lon=lon, method='nearest').values
                        humidity = float(np.mean(humidity_array))
                        year_data['humidity'].append(humidity)
                    
                    ds.close()
                except Exception as e:
                    print(f"  Error en SLV {year}: {e}")
                    continue
        
        # Procesar FLX (precipitación)
        if len(search_flx) > 0:
            files_flx = earthaccess.open(search_flx)
            
            for file in files_flx:
                try:
                    ds = xr.open_dataset(file, engine='h5netcdf')
                    
                    if 'time' in ds.dims and len(ds.time) > 1:
                        hours = [pd.to_datetime(t).hour for t in ds.time.values]
                        closest_idx = min(range(len(hours)), key=lambda i: abs(hours[i] - target_hour))
                        ds = ds.isel(time=closest_idx)
                    
                    precip_vars = ['PRECTOTCORR', 'PRECTOT', 'PRECCON', 'PRECSNO']
                    for var in precip_vars:
                        if var in ds:
                            precip_array = ds[var].sel(lat=lat, lon=lon, method='nearest').values
                            precip = float(np.mean(precip_array))
                            year_data['precip'].append(precip)
                            break
                    
                    ds.close()
                except Exception as e:
                    print(f"  Error en FLX {year}: {e}")
                    continue
        
        print(f"✓ {year}: T={len(year_data['temps'])}, P={len(year_data['precip'])}, W={len(year_data['wind'])}")
        
    except Exception as e:
        print(f"Error procesando año {year}: {e}")
    
    return year_data

@app.route('/api/calculate-probability', methods=['POST'])
def calculate_probability():
    try:
        data = request.json
        date = data['date']
        time = data['time']
        lat = float(data['lat'])
        lon = float(data['lon'])
        conditions = data['conditions']
        
        print(f"\n{'='*60}")
        print(f"NUEVA CONSULTA")
        print(f"Ubicación: {lat}, {lon}")
        print(f"Fecha: {date} {time}")
        print(f"Condiciones: {conditions}")
        print(f"{'='*60}\n")
        
        target_date = datetime.strptime(date, '%Y-%m-%d')
        month = target_date.month
        day = target_date.day
        target_hour = int(time.split(':')[0])
        
        years = range(2020, 2023)
        bbox = (lon - 0.5, lat - 0.5, lon + 0.5, lat + 0.5)
        
        results = {
            'location': f"{lat}, {lon}",
            'date': date,
            'time': time,
            'probabilities': {}
        }
        
        # Verificar cache
        cache_key = get_cache_key(lat, lon, month, day, target_hour)
        cached_data = load_from_cache(cache_key)
        
        if cached_data:
            historical_temps = cached_data['temps']
            historical_precip = cached_data['precip']
            historical_wind = cached_data['wind']
            historical_humidity = cached_data.get('humidity', [])
        else:
            print("Consultando NASA (puede tomar 15-30 segundos)...")
            
            historical_temps = []
            historical_precip = []
            historical_wind = []
            historical_humidity = []
            
            # Procesar años en paralelo
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {
                    executor.submit(process_year, year, month, day, target_hour, lat, lon, bbox): year 
                    for year in years
                }
                
                for future in as_completed(futures):
                    year_data = future.result()
                    historical_temps.extend(year_data['temps'])
                    historical_precip.extend(year_data['precip'])
                    historical_wind.extend(year_data['wind'])
                    historical_humidity.extend(year_data['humidity'])
            
            # Guardar en cache
            save_to_cache(cache_key, {
                'temps': historical_temps,
                'precip': historical_precip,
                'wind': historical_wind,
                'humidity': historical_humidity
            })
        
        print(f"\n{'='*60}")
        print(f"DATOS RECOPILADOS:")
        print(f"   Temperaturas: {len(historical_temps)} registros")
        print(f"   Precipitación: {len(historical_precip)} registros")
        print(f"   Viento: {len(historical_wind)} registros")
        print(f"{'='*60}\n")
        
        total_years = len(years)
        
        # LLUVIA
        if 'rain' in conditions:
            if historical_precip and len(historical_precip) > 0:
                precip_mm_day = [p * 86400 for p in historical_precip]
                rainy_days = sum(1 for p in precip_mm_day if p > 1.0)
                
                results['probabilities']['rain'] = {
                    'probability': round((rainy_days / len(precip_mm_day)) * 100, 1),
                    'avgDays': round((rainy_days / total_years) * 30, 1),
                    'maxRecorded': round(max(precip_mm_day), 1),
                    'message': get_positive_message('rain', (rainy_days / len(precip_mm_day)) * 100)
                }
            else:
                results['probabilities']['rain'] = {
                    'error': 'No hay datos históricos disponibles',
                    'message': 'No se pudieron obtener datos de precipitación para este período y ubicación'
                }
        
        # TEMPERATURA
        if 'temperature' in conditions:
            if historical_temps and len(historical_temps) > 0:
                avg_temp = np.mean(historical_temps)
                min_temp = np.min(historical_temps)
                max_temp = np.max(historical_temps)
                results['probabilities']['temperature'] = {
                    'avg': round(avg_temp, 1),
                    'min': round(min_temp, 1),
                    'max': round(max_temp, 1),
                    'message': get_positive_message('temperature', avg_temp)
                }
            else:
                results['probabilities']['temperature'] = {
                    'error': 'No hay datos históricos disponibles',
                    'message': 'No se pudieron obtener datos de temperatura para este período y ubicación'
                }
        
        # LLUVIA EXTREMA
        if 'extreme_rain' in conditions:
            if historical_precip and len(historical_precip) > 0:
                precip_mm_day = [p * 86400 for p in historical_precip]
                extreme_days = sum(1 for p in precip_mm_day if p > 20.0)
                
                results['probabilities']['extreme_rain'] = {
                    'probability': round((extreme_days / len(precip_mm_day)) * 100, 1),
                    'avgDays': round((extreme_days / total_years) * 30, 1),
                    'maxRecorded': round(max(precip_mm_day), 1),
                    'message': get_positive_message('extreme_rain', (extreme_days / len(precip_mm_day)) * 100)
                }
            else:
                results['probabilities']['extreme_rain'] = {
                    'error': 'No hay datos históricos disponibles',
                    'message': 'No se pudieron obtener datos de precipitación extrema para este período y ubicación'
                }
        
        # OLA DE CALOR
        if 'heat_wave' in conditions:
            if historical_temps and len(historical_temps) > 0:
                hot_days = sum(1 for t in historical_temps if t > 30)
                results['probabilities']['heat_wave'] = {
                    'probability': round((hot_days / len(historical_temps)) * 100, 1),
                    'avgDays': round((hot_days / total_years) * 30, 1),
                    'maxTemp': round(max(historical_temps), 1),
                    'message': get_positive_message('heat_wave', (hot_days / len(historical_temps)) * 100)
                }
            else:
                results['probabilities']['heat_wave'] = {
                    'error': 'No hay datos históricos disponibles',
                    'message': 'No se pudieron obtener datos de temperatura para calcular olas de calor'
                }
        
        # VIENTO
        if 'wind' in conditions:
            if historical_wind and len(historical_wind) > 0:
                windy_days = sum(1 for w in historical_wind if w > 8)
                results['probabilities']['wind'] = {
                    'probability': round((windy_days / len(historical_wind)) * 100, 1),
                    'avgSpeed': round(np.mean(historical_wind), 1),
                    'maxSpeed': round(max(historical_wind), 1),
                    'message': get_positive_message('wind', (windy_days / len(historical_wind)) * 100)
                }
            else:
                results['probabilities']['wind'] = {
                    'error': 'No hay datos históricos disponibles',
                    'message': 'No se pudieron obtener datos de viento para este período y ubicación'
                }
        
        # FRÍO EXTREMO
        if 'cold' in conditions:
            if historical_temps and len(historical_temps) > 0:
                cold_days = sum(1 for t in historical_temps if t < 3)
                results['probabilities']['cold'] = {
                    'probability': round((cold_days / len(historical_temps)) * 100, 1),
                    'avgDays': round((cold_days / total_years) * 30, 1),
                    'minTemp': round(min(historical_temps), 1),
                    'message': get_positive_message('cold', (cold_days / len(historical_temps)) * 100)
                }
            else:
                results['probabilities']['cold'] = {
                    'error': 'No hay datos históricos disponibles',
                    'message': 'No se pudieron obtener datos de temperatura para calcular frío extremo'
                }
        
        print(f"\nRESULTADOS CALCULADOS")
        print(json.dumps(results, indent=2, ensure_ascii=False))
        print(f"{'='*60}\n")
        
        return jsonify(results)
        
    except Exception as e:
        print(f"\nError general: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def get_positive_message(condition, value):
    """Generar mensajes positivos según la condición"""
    messages = {
        'rain': {
            'low': 'Cielo mayormente despejado. Perfecto para actividades al aire libre',
            'medium': 'Perfecta oportunidad para disfrutar del sonido de la lluvia',
            'high': 'Excelente para la naturaleza. Los ecosistemas agradecen el agua'
        },
        'temperature': {
            'cold': 'Clima fresco ideal para mantenerte activo',
            'mild': 'Temperatura perfecta para cualquier actividad',
            'warm': 'Clima cálido ideal para disfrutar el aire libre'
        },
        'extreme_rain': {
            'low': 'Probabilidad muy baja. Disfruta con tranquilidad',
            'medium': 'Mantente informado, pero sin preocupaciones',
            'high': 'Espectáculo natural en potencia. La naturaleza en acción'
        },
        'heat_wave': {
            'low': 'Clima agradable sin temperaturas extremas',
            'medium': 'Perfecto para los amantes del calor',
            'high': 'Ideal para la playa y piscina'
        },
        'wind': {
            'low': 'Ambiente tranquilo y apacible',
            'medium': 'Perfecto para volar cometas o hacer windsurf',
            'high': 'Los amantes del viento lo disfrutarán'
        },
        'cold': {
            'low': 'Muy baja probabilidad de frío extremo',
            'medium': 'Oportunidad para disfrutar ropa abrigada y bebidas calientes',
            'high': 'Posible clima invernal para los amantes del frío'
        }
    }
    
    if condition == 'temperature':
        if value < 15:
            return messages['temperature']['cold']
        elif value < 25:
            return messages['temperature']['mild']
        else:
            return messages['temperature']['warm']
    else:
        if value < 20:
            return messages[condition]['low']
        elif value < 50:
            return messages[condition]['medium']
        else:
            return messages[condition]['high']


if __name__ == '__main__':
    app.run(debug=True, port=5000)
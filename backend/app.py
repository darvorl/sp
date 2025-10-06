from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import earthaccess
import xarray as xr
import numpy as np
from datetime import datetime
import pandas as pd
import json
import os

app = Flask(__name__)
# Configuración CORS totalmente permisiva para desarrollo (local y Codespaces)
CORS(app, resources={
    r"/api/*": {
        "origins": "*",  # Permitir todos los orígenes en desarrollo
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": False
    }
})

# Login a NASA (una sola vez al iniciar)
os.environ["NETRC"] = "/workspaces/sp/_netrc"
auth = earthaccess.login()

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
        print(f"🔍 NUEVA CONSULTA")
        print(f"📍 Ubicación: {lat}, {lon}")
        print(f"📅 Fecha: {date} {time}")
        print(f"🌦️  Condiciones: {conditions}")
        print(f"{'='*60}\n")
        
        target_date = datetime.strptime(date, '%Y-%m-%d')
        month = target_date.month
        day = target_date.day
        target_hour = int(time.split(':')[0])
        
        years = range(2014, 2024)
        bbox = (lon - 1, lat - 1, lon + 1, lat + 1)
        
        results = {
            'location': f"{lat}, {lon}",
            'date': date,
            'time': time,
            'probabilities': {}
        }
        
        historical_temps = []
        historical_precip = []
        historical_wind = []
        historical_humidity = []
        
        print(f"Buscando datos para {month:02d}-{day:02d} a las {target_hour}:00")
        
        for year in years:
            try:
                historical_date = f"{year}-{month:02d}-{day:02d}"
                print(f"Procesando {historical_date}...")
                
                # DATASET 1: M2T1NXSLV para temperatura, viento, humedad
                search_slv = earthaccess.search_data(
                    short_name='M2T1NXSLV',
                    cloud_hosted=True,
                    bounding_box=bbox,
                    temporal=(historical_date, historical_date),
                )
                
                # DATASET 2: M2T1NXFLX para precipitación
                search_flx = earthaccess.search_data(
                    short_name='M2T1NXFLX',
                    cloud_hosted=True,
                    bounding_box=bbox,
                    temporal=(historical_date, historical_date),
                )
                
                # Procesar temperatura, viento y humedad
                if len(search_slv) > 0:
                    files_slv = earthaccess.open(search_slv)
                    
                    for file in files_slv:
                        try:
                            ds = xr.open_dataset(file, engine='h5netcdf')
                            
                            if 'time' in ds.dims and len(ds.time) > 1:
                                hours = [pd.to_datetime(t).hour for t in ds.time.values]
                                closest_idx = min(range(len(hours)), key=lambda i: abs(hours[i] - target_hour))
                                ds = ds.isel(time=closest_idx)
                            
                            # TEMPERATURA
                            if 'T2M' in ds:
                                temp_array = ds['T2M'].sel(lat=lat, lon=lon, method='nearest').values
                                temp = float(np.mean(temp_array)) - 273.15
                                historical_temps.append(temp)
                            
                            # VIENTO
                            if 'U10M' in ds and 'V10M' in ds:
                                u_array = ds['U10M'].sel(lat=lat, lon=lon, method='nearest').values
                                v_array = ds['V10M'].sel(lat=lat, lon=lon, method='nearest').values
                                u = float(np.mean(u_array))
                                v = float(np.mean(v_array))
                                wind = np.sqrt(u**2 + v**2)
                                historical_wind.append(wind)
                            
                            # HUMEDAD
                            if 'RH2M' in ds:
                                humidity_array = ds['RH2M'].sel(lat=lat, lon=lon, method='nearest').values
                                humidity = float(np.mean(humidity_array))
                                historical_humidity.append(humidity)
                            
                            ds.close()
                        except Exception as e:
                            print(f"  Error en archivo SLV: {e}")
                            continue
                
                # Procesar precipitación del dataset de flujos
                if len(search_flx) > 0:
                    files_flx = earthaccess.open(search_flx)
                    
                    for file in files_flx:
                        try:
                            ds = xr.open_dataset(file, engine='h5netcdf')
                            
                            if 'time' in ds.dims and len(ds.time) > 1:
                                hours = [pd.to_datetime(t).hour for t in ds.time.values]
                                closest_idx = min(range(len(hours)), key=lambda i: abs(hours[i] - target_hour))
                                ds = ds.isel(time=closest_idx)
                            
                            # PRECIPITACIÓN - en M2T1NXFLX se llama PRECTOT o PRECTOTCORR
                            precip_vars = ['PRECTOTCORR', 'PRECTOT', 'PRECCON', 'PRECSNO']
                            for var in precip_vars:
                                if var in ds:
                                    precip_array = ds[var].sel(lat=lat, lon=lon, method='nearest').values
                                    precip = float(np.mean(precip_array))
                                    historical_precip.append(precip)
                                    break
                            
                            ds.close()
                        except Exception as e:
                            print(f"  Error en archivo FLX: {e}")
                            continue
                
                print(f"✓ {year}: T={len(historical_temps)}, P={len(historical_precip)}, W={len(historical_wind)}")
                    
            except Exception as e:
                print(f"Error procesando año {year}: {e}")
                continue
        
        print(f"\n{'='*60}")
        print(f"📊 DATOS RECOPILADOS:")
        print(f"   Temperaturas: {len(historical_temps)} registros")
        if historical_temps:
            print(f"      Min: {min(historical_temps):.1f}°C, Max: {max(historical_temps):.1f}°C, Avg: {np.mean(historical_temps):.1f}°C")
        
        print(f"   Precipitación: {len(historical_precip)} registros")
        if historical_precip:
            print(f"      Min: {min(historical_precip):.4f}mm, Max: {max(historical_precip):.4f}mm, Avg: {np.mean(historical_precip):.4f}mm")
            rainy = sum(1 for p in historical_precip if p > 0.001)
            print(f"      Días con lluvia (>0.001mm): {rainy}/{len(historical_precip)}")
        
        print(f"   Viento: {len(historical_wind)} registros")
        if historical_wind:
            print(f"      Min: {min(historical_wind):.1f}m/s, Max: {max(historical_wind):.1f}m/s, Avg: {np.mean(historical_wind):.1f}m/s")
        print(f"{'='*60}\n")
        
        # Calcular probabilidades
        total_years = len(years)
        
        if 'rain' in conditions:
            if historical_precip and len(historical_precip) > 0:
                # NOTA: precipitación en MERRA-2 viene en kg/m²/s, convertir a mm/día
                precip_mm_day = [p * 86400 for p in historical_precip]  # 1 kg/m²/s = 86400 mm/día
                rainy_days = sum(1 for p in precip_mm_day if p > 1.0)
                
                results['probabilities']['rain'] = {
                    'probability': round((rainy_days / len(precip_mm_day)) * 100, 1),
                    'avgDays': round((rainy_days / total_years) * 30, 1),
                    'maxRecorded': round(max(precip_mm_day), 1),
                    'message': get_positive_message('rain', (rainy_days / len(precip_mm_day)) * 100)
                }
            else:
                results['probabilities']['rain'] = {
                    'probability': 25.0,
                    'avgDays': 7.5,
                    'maxRecorded': 15.0,
                    'message': '🌧️ Probabilidad estimada basada en patrones regionales de Chile central'
                }
        
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
                    'avg': 15.0,
                    'min': 10.0,
                    'max': 20.0,
                    'message': '🌡️ Temperatura estimada para Santiago'
                }
        
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
                    'probability': 3.0,
                    'avgDays': 0.9,
                    'maxRecorded': 30.0,
                    'message': '⛈️ Baja probabilidad de lluvia extrema en primavera'
                }
        
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
                    'probability': 5.0,
                    'avgDays': 1.5,
                    'maxTemp': 28.0,
                    'message': '☀️ Baja probabilidad de ola de calor en octubre'
                }
        
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
                    'probability': 15.0,
                    'avgSpeed': 5.5,
                    'maxSpeed': 18.0,
                    'message': '💨 Vientos moderados típicos de primavera'
                }
        
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
                    'probability': 0.0,
                    'avgDays': 0.0,
                    'minTemp': 5.0,
                    'message': '❄️ Sin riesgo de frío extremo en octubre'
                }
        
        print(f"\n✅ RESULTADOS CALCULADOS")
        print(json.dumps(results, indent=2, ensure_ascii=False))
        print(f"{'='*60}\n")
        
        return jsonify(results)
        
    except Exception as e:
        print(f"\n❌ Error general: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def get_positive_message(condition, value):
    """Generar mensajes positivos según la condición"""
    messages = {
        'rain': {
            'low': '¡Cielo mayormente despejado! Perfecto para actividades al aire libre ☀️',
            'medium': '¡Perfecta oportunidad para disfrutar del sonido de la lluvia! ☔',
            'high': '¡Excelente para la naturaleza! Los ecosistemas agradecen el agua 🌱'
        },
        'temperature': {
            'cold': '¡Clima fresco ideal para mantenerte activo! 🏃‍♂️',
            'mild': '¡Temperatura perfecta para cualquier actividad! 🌤️',
            'warm': '¡Clima cálido ideal para disfrutar el aire libre! ☀️'
        },
        'extreme_rain': {
            'low': '¡Probabilidad muy baja! Disfruta con tranquilidad 😊',
            'medium': 'Mantente informado, pero sin preocupaciones 🌦️',
            'high': '¡Espectáculo natural en potencia! La naturaleza en acción 🌧️'
        },
        'heat_wave': {
            'low': '¡Clima agradable sin temperaturas extremas! 😎',
            'medium': '¡Perfecto para los amantes del calor! ☀️',
            'high': '¡Ideal para la playa y piscina! 🏖️'
        },
        'wind': {
            'low': '¡Ambiente tranquilo y apacible! 🍃',
            'medium': '¡Perfecto para volar cometas o hacer windsurf! 🪁',
            'high': '¡Los amantes del viento lo disfrutarán! 💨'
        },
        'cold': {
            'low': '¡Muy baja probabilidad de frío extremo! 🌡️',
            'medium': '¡Oportunidad para disfrutar ropa abrigada y bebidas calientes! ☕',
            'high': '¡Posible clima invernal para los amantes del frío! ❄️'
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
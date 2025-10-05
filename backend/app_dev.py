from flask import Flask, request, jsonify
from flask_cors import CORS
import random
from datetime import datetime
import json

app = Flask(__name__)
# Configuración CORS totalmente permisiva para desarrollo
CORS(app, resources={
    r"/api/*": {
        "origins": "*",  # Permitir todos los orígenes en desarrollo
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": False
    }
})

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
        print(f"🔍 NUEVA CONSULTA (MODO DESARROLLO)")
        print(f"📍 Ubicación: {lat}, {lon}")
        print(f"📅 Fecha: {date} {time}")
        print(f"🌦️  Condiciones: {conditions}")
        print(f"{'='*60}\n")
        
        # Datos simulados para desarrollo
        results = {
            'location': f"{lat}, {lon}",
            'date': date,
            'time': time,
            'probabilities': {}
        }
        
        # Generar datos simulados pero realistas para cada condición
        if 'rain' in conditions:
            probability = random.uniform(15, 35)  # 15-35% probabilidad de lluvia
            results['probabilities']['rain'] = {
                'probability': round(probability, 1),
                'avgDays': round(probability * 0.3, 1),  # Aproximadamente 30% de los días de probabilidad
                'maxRecorded': round(random.uniform(5, 25), 1),
                'message': get_positive_message('rain', probability)
            }
        
        if 'temperature' in conditions:
            # Temperatura típica para Santiago en la fecha dada
            base_temp = 18 if datetime.strptime(date, '%Y-%m-%d').month in [9, 10, 11] else 15
            avg_temp = base_temp + random.uniform(-3, 5)
            min_temp = avg_temp - random.uniform(5, 8)
            max_temp = avg_temp + random.uniform(5, 10)
            
            results['probabilities']['temperature'] = {
                'avg': round(avg_temp, 1),
                'min': round(min_temp, 1),
                'max': round(max_temp, 1),
                'message': get_positive_message('temperature', avg_temp)
            }
        
        if 'extreme_rain' in conditions:
            probability = random.uniform(2, 8)  # 2-8% probabilidad de lluvia extrema
            results['probabilities']['extreme_rain'] = {
                'probability': round(probability, 1),
                'avgDays': round(probability * 0.2, 1),
                'maxRecorded': round(random.uniform(20, 50), 1),
                'message': get_positive_message('extreme_rain', probability)
            }
        
        if 'heat_wave' in conditions:
            probability = random.uniform(3, 12)  # 3-12% probabilidad de ola de calor
            results['probabilities']['heat_wave'] = {
                'probability': round(probability, 1),
                'avgDays': round(probability * 0.25, 1),
                'maxTemp': round(random.uniform(28, 35), 1),
                'message': get_positive_message('heat_wave', probability)
            }
        
        if 'wind' in conditions:
            probability = random.uniform(10, 25)  # 10-25% probabilidad de viento fuerte
            results['probabilities']['wind'] = {
                'probability': round(probability, 1),
                'avgSpeed': round(random.uniform(4, 8), 1),
                'maxSpeed': round(random.uniform(15, 25), 1),
                'message': get_positive_message('wind', probability)
            }
        
        if 'cold' in conditions:
            probability = random.uniform(0, 5)  # 0-5% probabilidad de frío extremo
            results['probabilities']['cold'] = {
                'probability': round(probability, 1),
                'avgDays': round(probability * 0.1, 1),
                'minTemp': round(random.uniform(0, 5), 1),
                'message': get_positive_message('cold', probability)
            }
        
        print(f"\n✅ RESULTADOS SIMULADOS")
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


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'ok', 
        'mode': 'development',
        'message': '🛠️ Backend SpaceRain - Modo Desarrollo (datos simulados)'
    })


if __name__ == '__main__':
    print("\n" + "="*80)
    print("🛠️  SPACERAIN BACKEND - MODO DESARROLLO")
    print("="*80)
    print("📡 Este servidor usa datos simulados para desarrollo")
    print("🔗 API disponible en: http://localhost:5000")
    print("🌐 CORS habilitado para todos los orígenes")
    print("="*80 + "\n")
    
    app.run(debug=True, port=5000, host='0.0.0.0')
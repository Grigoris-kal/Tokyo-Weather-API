from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pytz
import os
import requests
import time
from pathlib import Path

# Load environment variables
# Try to load from local file first, but don't fail if it doesn't exist (for Render deployment)
try:
    dotenv_path = Path(__file__).parent / "Tokyo_Rainfall.env"
    load_dotenv(dotenv_path=dotenv_path)
except:
    pass  # On Render, env vars are set through dashboard

# Configuration
LAT = os.getenv("LAT", "35.6895")
LON = os.getenv("LON", "139.6917")
API_KEY = os.getenv("OPENWEATHER_API_KEY")

# Debug: Print environment variables (without showing the full API key)
print(f"🔧 Environment check:")
print(f"   LAT = {LAT}")
print(f"   LON = {LON}")
print(f"   API_KEY = {'✅ Set' if API_KEY else '❌ Missing'}")
if API_KEY:
    print(f"   API_KEY starts with: {API_KEY[:8]}...")

# Initialize FastAPI
app = FastAPI()
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Serve static files
app.mount("/static", StaticFiles(directory="static_images"), name="static")

# IMPROVED CACHING SYSTEM
WEATHER_CACHE = {
    'data': None,
    'timestamp': 0,
    'in_progress': False  # Prevent duplicate requests
}
CACHE_DURATION = 7200  # 2 hours in seconds (longer cache)

def is_cache_valid():
    """Check if cache is still valid"""
    current_time = time.time()
    return (WEATHER_CACHE['data'] is not None and 
            current_time - WEATHER_CACHE['timestamp'] < CACHE_DURATION)

def get_cache_status():
    """Get human-readable cache status"""
    if WEATHER_CACHE['data'] is None:
        return "No cache"
    
    current_time = time.time()
    age_minutes = (current_time - WEATHER_CACHE['timestamp']) / 60
    
    if is_cache_valid():
        return f"Cached data ({age_minutes:.0f} min old)"
    else:
        return "Cache expired"

# Root route - redirect to main weather page
@app.get("/")
def root():
    return {"message": "Tokyo Weather API", "main_page": "/rainfall/formatted"}

# Health check route
@app.get("/health")
def health_check():
    return {"status": "healthy", "api_key_loaded": bool(API_KEY)}

def get_all_weather_data():
    """Consolidated function that makes only 3 API calls instead of 5+"""
    
    # Check cache first
    if is_cache_valid() and WEATHER_CACHE['data'] is not None:
        print("📋 Using cached weather data")
        return WEATHER_CACHE['data']
    
    # Prevent duplicate requests if one is already in progress
    if WEATHER_CACHE['in_progress']:
        print("⏳ Request in progress, waiting for cache...")
        # Return existing data if available, even if expired
        if WEATHER_CACHE['data'] is not None:
            return WEATHER_CACHE['data']
    
    WEATHER_CACHE['in_progress'] = True
    print("🔄 Fetching fresh weather data (consolidated)")
    
    try:
        tokyo_tz = pytz.timezone("Asia/Tokyo")
        now = datetime.now(tokyo_tz)
        
        # API Call 1: Current Weather (also has sunrise/sunset)
        print("🌐 API Call 1/3: Current weather")
        current_url = f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}&appid={API_KEY}&units=metric"
        current_response = requests.get(current_url)
        current_data = current_response.json()
        
        # API Call 2: 5-day Forecast (also has rainfall data)
        print("🌐 API Call 2/3: 5-day forecast")
        forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={LAT}&lon={LON}&appid={API_KEY}&units=metric"
        forecast_response = requests.get(forecast_url)
        forecast_data = forecast_response.json()
        
        # API Call 3: Air Quality
        print("🌐 API Call 3/3: Air quality")
        air_url = f"https://api.openweathermap.org/data/2.5/air_pollution?lat={LAT}&lon={LON}&appid={API_KEY}"
        air_response = requests.get(air_url)
        air_data = air_response.json()
        
        # Process Current Weather
        current_weather = {
            "temp": current_data["main"]["temp"],
            "humidity": current_data["main"]["humidity"],
            "wind_speed": current_data["wind"]["speed"],
            "wind_deg": current_data["wind"].get("deg", 0),
            "weather": current_data["weather"][0]["main"],
            "description": current_data["weather"][0]["description"].capitalize(),
            "icon": current_data["weather"][0]["icon"]
        }
        
        # Process Sun/Moon Data (from current weather API)
        sunrise = datetime.fromtimestamp(current_data["sys"]["sunrise"], tz=pytz.utc).astimezone(tokyo_tz)
        sunset = datetime.fromtimestamp(current_data["sys"]["sunset"], tz=pytz.utc).astimezone(tokyo_tz)
        moon_phases = ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘"]
        moon_phase = moon_phases[sunset.day % 8]
        
        sun_moon = {
            "sunrise": sunrise.strftime("%H:%M"),
            "sunset": sunset.strftime("%H:%M"),
            "moon": moon_phase
        }
        
        # Process Rainfall Data (from forecast API)
        rainfall_forecast = []
        current_rainfall = 0.0
        
        for item in forecast_data['list']:
            dt_utc = datetime.strptime(item['dt_txt'], "%Y-%m-%d %H:%M:%S")
            dt_utc = pytz.utc.localize(dt_utc)
            dt_tokyo = dt_utc.astimezone(tokyo_tz)
            if dt_tokyo > now:
                rainfall = item.get('rain', {}).get('3h', 0.0)
                if rainfall > 0:
                    rainfall_forecast.append({
                        "timestamp": dt_tokyo.strftime('%Y-%m-%d %H:%M:%S JST%z'),
                        "rainfall_3h_mm": rainfall
                    })
        
        if forecast_data['list']:
            last_rain = forecast_data['list'][0].get('rain', {}).get('3h', 0.0)
            current_rainfall = last_rain
        
        rainfall_data = {
            "current_rainfall_last_hour_mm": current_rainfall,
            "current_timestamp": now.strftime('%Y-%m-%d %H:%M:%S JST%z'),
            "forecast": rainfall_forecast[:4]
        }
        
        # Process 5-day Forecast (from forecast API)
        daily_data = {}
        for item in forecast_data['list']:
            date = item['dt_txt'].split()[0]
            if date not in daily_data:
                daily_data[date] = {
                    "temp": item["main"]["temp"],
                    "description": item["weather"][0]["description"].capitalize(),
                    "icon": item["weather"][0]["icon"],
                    "date": datetime.strptime(date, "%Y-%m-%d").strftime("%a, %b %d")
                }
        
        forecast = list(daily_data.values())[:5]
        
        # Process Air Quality
        aqi = air_data['list'][0]['main']['aqi']
        levels = {
            1: ("Good", "Air quality is satisfactory.", "#4CAF50"),
            2: ("Fair", "Moderate quality.", "#8BC34A"),
            3: ("Moderate", "Sensitive groups affected.", "#FFC107"),
            4: ("Poor", "Unhealthy for some.", "#FF9800"),
            5: ("Very Poor", "Health alert.", "#F44336")
        }
        air_quality = {
            "aqi": aqi,
            "level": levels.get(aqi, ("Unknown", "No data", "#9E9E9E"))[0],
            "advice": levels.get(aqi, ("Unknown", "No data", "#9E9E9E"))[1],
            "color": levels.get(aqi, ("Unknown", "No data", "#9E9E9E"))[2],
            "components": air_data['list'][0]['components']
        }
        
        # Consolidate all data
        all_data = {
            'current_weather': current_weather,
            'sun_moon': sun_moon,
            'rainfall_data': rainfall_data,
            'forecast': forecast,
            'air_quality': air_quality
        }
        
        # Update cache
        WEATHER_CACHE['data'] = all_data
        WEATHER_CACHE['timestamp'] = time.time()
        WEATHER_CACHE['in_progress'] = False
        
        print("✅ All weather data cached successfully")
        return all_data
        
    except Exception as e:
        print(f"❌ Error fetching weather data: {e}")
        WEATHER_CACHE['in_progress'] = False
        
        # Return fallback data
        return {
            'current_weather': {
                "temp": "N/A", "humidity": "N/A", "wind_speed": "N/A", 
                "wind_deg": 0, "weather": "Unknown", "description": "Weather unavailable", "icon": "01d"
            },
            'sun_moon': {"sunrise": "N/A", "sunset": "N/A", "moon": "🌑"},
            'rainfall_data': {
                "current_rainfall_last_hour_mm": 0.0,
                "current_timestamp": datetime.now(pytz.timezone("Asia/Tokyo")).strftime('%Y-%m-%d %H:%M:%S JST%z'),
                "forecast": []
            },
            'forecast': [],
            'air_quality': {
                "aqi": 0, "level": "Unknown", "advice": "No air quality data", 
                "color": "#9E9E9E", "components": {}
            }
        }

def wind_direction(degrees):
    directions = ["↓ N", "↙ NE", "← E", "↖ SE", "↑ S", "↗ SW", "→ W", "↘ NW"]
    return directions[round((degrees % 360) / 45) % 8]

@app.api_route("/rainfall/formatted", response_class=HTMLResponse, methods=["GET", "HEAD"])
def rainfall_formatted(request: Request):
    # Get all data with just 3 API calls instead of 5+
    all_data = get_all_weather_data()
    
    rainfall_data = all_data['rainfall_data']
    weather = all_data['current_weather']
    forecast = all_data['forecast']
    air_quality = all_data['air_quality']
    sun_moon = all_data['sun_moon']
    wind_dir = wind_direction(weather["wind_deg"])
    
    html_content = f"""
    <html>
        <head>
            <title>Tokyo Weather</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
            <style>
                body {{
                    font-family: 'Arial', sans-serif;
                    background-image: url('/static/tokyo_fuji.jpg');
                    background-size: cover;
                    background-attachment: fixed;
                    color: white;
                    margin: 0;
                    padding: 20px;
                }}
                .container {{
                    max-width: 1000px;
                    margin: 0 auto;
                }}
                .card {{
                    background: rgba(0, 0, 0, 0.7);
                    backdrop-filter: blur(5px);
                    border-radius: 15px;
                    padding: 25px;
                    margin-bottom: 20px;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.2);
                }}
                .weather-header {{
                    display: flex;
                    align-items: center;
                    margin-bottom: 20px;
                }}
                .weather-icon {{
                    width: 80px;
                    height: 80px;
                    margin-right: 20px;
                }}
                .weather-main {{
                    flex-grow: 1;
                }}
                .weather-temp {{
                    font-size: 2.5em;
                    font-weight: bold;
                    margin: 5px 0;
                }}
                .weather-desc {{
                    font-size: 1.2em;
                    opacity: 0.9;
                }}
                .details-grid {{
                    display: grid;
                    grid-template-columns: repeat(2, 1fr);
                    gap: 15px;
                    margin-top: 20px;
                }}
                .detail-item {{
                    display: flex;
                    align-items: center;
                    padding: 10px;
                    background: rgba(255,255,255,0.1);
                    border-radius: 8px;
                }}
                .detail-icon {{
                    font-size: 1.5em;
                    margin-right: 10px;
                    width: 30px;
                    text-align: center;
                }}
                .forecast-item {{
                    padding: 12px 0;
                    border-bottom: 1px solid rgba(255,255,255,0.2);
                    display: flex;
                    justify-content: space-between;
                }}
                .forecast-item:last-child {{
                    border-bottom: none;
                }}
                h1, h2, h3 {{
                    margin-top: 0;
                    text-shadow: 1px 1px 3px rgba(0,0,0,0.5);
                }}
                .highlight {{
                    color: #fff;
                    font-weight: bold;
                }}
                .aqi-display {{
                    padding: 8px 12px;
                    border-radius: 20px;
                    background-color: {air_quality['color']};
                    display: inline-block;
                    margin-left: 10px;
                }}
                .forecast-container {{
                    display: flex;
                    overflow-x: auto;
                    gap: 15px;
                    padding: 10px 0;
                }}
                .forecast-day {{
                    min-width: 120px;
                    text-align: center;
                    background: rgba(255,255,255,0.1);
                    padding: 10px;
                    border-radius: 8px;
                }}
                .forecast-day img {{
                    width: 50px;
                    height: 50px;
                }}
                #map {{
                    height: 400px;
                    width: 100%;
                    border-radius: 10px;
                    margin-top: 15px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 15px 0;
                }}
                th, td {{
                    padding: 12px;
                    text-align: left;
                    border-bottom: 1px solid rgba(255,255,255,0.2);
                }}
                th {{
                    background: rgba(255,255,255,0.1);
                }}
                .download-btn {{
                    display: block;
                    text-align: center;
                    margin: 20px auto;
                    padding: 10px 15px;
                    background: rgba(0, 100, 200, 0.7);
                    color: white;
                    border-radius: 5px;
                    text-decoration: none;
                    width: fit-content;
                }}
                .download-btn:hover {{
                    background: rgba(0, 120, 240, 0.9);
                }}
                .cache-info {{
                    background: rgba(0, 150, 0, 0.3);
                    padding: 10px;
                    border-radius: 8px;
                    margin-bottom: 10px;
                    text-align: center;
                    font-size: 0.9em;
                }}
                .optimization-banner {{
                    background: rgba(0, 200, 0, 0.8);
                    color: white;
                    padding: 10px;
                    text-align: center;
                    border-radius: 8px;
                    margin-bottom: 20px;
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                
                <!-- Optimization Status -->
                <div class="optimization-banner">
                    🚀 OPTIMIZED: Using only 3 API calls instead of 5+ | Cache: {get_cache_status()}
                </div>
                
                <!-- Current Weather Card -->
                <div class="card">
                    <div class="weather-header">
                        <img class="weather-icon" src="https://openweathermap.org/img/wn/{weather['icon']}@4x.png" alt="Weather icon">
                   <div class="weather-main">
                     <h1>Tokyo Weather</h1>
                     <div style="font-size: 1.1em; opacity: 0.9; margin-bottom: 5px; font-weight: 500;">
                          {datetime.now(pytz.timezone("Asia/Tokyo")).strftime('%A, %B %d, %Y')}
                     </div>
                      <div class="weather-desc">{weather['description']}</div>
                      <div class="weather-temp">{weather['temp']}°C</div>
                    </div>
                    </div>
                    
                    <div class="details-grid">
                        <div class="detail-item">
                            <div class="detail-icon">💧</div>
                            <div>Humidity <span class="highlight">{weather['humidity']}%</span></div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-icon">🌬️</div>
                            <div>Wind <span class="highlight">{weather['wind_speed']} m/s {wind_dir}</span></div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-icon">☀️</div>
                            <div>Sunrise <span class="highlight">{sun_moon['sunrise']}</span></div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-icon">🌇</div>
                            <div>Sunset <span class="highlight">{sun_moon['sunset']}</span></div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-icon">🌙</div>
                            <div>Moon Phase <span class="highlight">{sun_moon['moon']}</span></div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-icon">⏱️</div>
                            <div>Last Update <span class="highlight">{rainfall_data['current_timestamp']}</span></div>
                        </div>
                    </div>
                </div>
                
                <!-- Air Quality Card -->
                <div class="card">
                    <h2>Air Quality</h2>
                    <div style="display: flex; align-items: center;">
                        <div>Current AQI: </div>
                        <div class="aqi-display">{air_quality['level']} ({air_quality['aqi']})</div>
                    </div>
                    <p>{air_quality['advice']}</p>
                    
                    <table>
                        <tr>
                            <th>Pollutant</th>
                            <th>Concentration (μg/m³)</th>
                        </tr>
                        <tr>
                            <td>CO</td>
                            <td>{air_quality['components'].get('co', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td>NO</td>
                            <td>{air_quality['components'].get('no', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td>NO₂</td>
                            <td>{air_quality['components'].get('no2', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td>O₃</td>
                            <td>{air_quality['components'].get('o3', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td>SO₂</td>
                            <td>{air_quality['components'].get('so2', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td>PM2.5</td>
                            <td>{air_quality['components'].get('pm2_5', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td>PM10</td>
                            <td>{air_quality['components'].get('pm10', 'N/A')}</td>
                        </tr>
                    </table>
                </div>
                
                <!-- 5-Day Forecast Card -->
                <div class="card">
                    <h2>5-Day Forecast</h2>
                    <div class="forecast-container">
                        {"".join(
                            f'<div class="forecast-day">'
                            f'<div>{day["date"]}</div>'
                            f'<img src="https://openweathermap.org/img/wn/{day["icon"]}@2x.png" alt="{day["description"]}">'
                            f'<div>{day["temp"]}°C</div>'
                            f'<div style="font-size:0.9em">{day["description"]}</div>'
                            f'</div>'
                            for day in forecast
                        )}
                    </div>
                </div>
                
                <!-- Rainfall Forecast Card -->
                <div class="card">
                    <h2>Rainfall Forecast</h2>
                    <div class="highlight" style="font-size: 1.2em; margin-bottom: 15px;">
                        Current: {rainfall_data['current_rainfall_last_hour_mm']} mm
                    </div>
                    
                    <table>
                        <tr>
                            <th>Time</th>
                            <th>Rainfall (mm)</th>
                        </tr>
                        {"".join(
                            f'<tr>'
                            f'<td>{f["timestamp"]}</td>'
                            f'<td>{f["rainfall_3h_mm"]} mm</td>'
                            f'</tr>'
                            for f in rainfall_data["forecast"]
                        )}
                    </table>
                </div>
                
                <!-- Interactive Map Card -->
                <div class="card">
                    <h2>Interactive Weather Map</h2>
                    <p>Precipitation map showing rain intensity in Tokyo area</p>
                    <div id="map"></div>
                    <div class="map-legend">
                        <h3>Rain Intensity</h3>
                        <div>🔵 Light (0-2mm/h)</div>
                        <div>🔷 Moderate (2-10mm/h)</div>
                        <div>🔶 Heavy (10-50mm/h)</div>
                        <div>🔴 Extreme (>50mm/h)</div>
                    </div>
                </div>

                <!-- Download Button -->
                <a href="/download" class="download-btn">
                    📥 Download API Source Code
                </a>
            </div>
            
            <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
            <script>
                // Initialize map centered on Tokyo
                var map = L.map('map').setView([{LAT}, {LON}], 11);
                
                // Add base map layer
                L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                }}).addTo(map);
                
                // Add weather overlay
                L.tileLayer('https://tile.openweathermap.org/map/precipitation_new/{{z}}/{{x}}/{{y}}.png?appid={API_KEY}', {{
                    attribution: 'Weather data © OpenWeatherMap',
                    opacity: 0.7
                }}).addTo(map);
                
                // Add marker for Tokyo location
                L.marker([{LAT}, {LON}]).addTo(map)
                    .bindPopup('Tokyo<br>Current Location');
            </script>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/download")
def download_api():
    """Download the API source code"""
    return FileResponse(
        path=__file__,
        filename="Tokyo_Weather_API.py",
        media_type="text/x-python"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

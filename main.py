import os
import math
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(title="Weather API", version="1.4")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.getenv("WEATHER_API_KEY")

# ============================================================
# Utility Helpers
# ============================================================

def validate_units(units: str):
    return units if units in ("metric", "imperial") else "metric"


def geocode_city(city):
    """Return (lat, lon, name, country) or 404."""
    url = "http://api.openweathermap.org/geo/1.0/direct"
    params = {"q": city, "limit": 1, "appid": API_KEY}
    r = requests.get(url, params=params)
    data = r.json()
    if not data:
        raise HTTPException(404, "City not found")
    return data[0]["lat"], data[0]["lon"], data[0]["name"], data[0].get("country", "")


def one_call(lat, lon, units="metric", exclude=""):
    """Safe OneCall wrapper."""
    url = "https://api.openweathermap.org/data/2.5/onecall"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": API_KEY,
        "units": units,
        "exclude": exclude,
    }
    r = requests.get(url, params=params)
    if r.status_code != 200:
        return {}
    return r.json()


# ============================================================
# Current Weather
# ============================================================

@app.get("/weather")
def get_weather(city: str, units: str = "metric"):
    units = validate_units(units)
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": API_KEY, "units": units}

    r = requests.get(url, params=params)
    if r.status_code != 200:
        raise HTTPException(404, "City not found")

    data = r.json()

    return {
        "city": data["name"],
        "temperature": data["main"]["temp"],
        "feels_like": data["main"]["feels_like"],
        "temp_min": data["main"]["temp_min"],
        "temp_max": data["main"]["temp_max"],
        "humidity": data["main"]["humidity"],
        "wind_speed": data["wind"]["speed"],
        "sunrise": data["sys"]["sunrise"],
        "sunset": data["sys"]["sunset"],
        "condition": data["weather"][0]["description"],
        "icon": data["weather"][0]["icon"],
        "rain_1h": data.get("rain", {}).get("1h"),
        "rain_3h": data.get("rain", {}).get("3h"),
        "snow_1h": data.get("snow", {}).get("1h"),
        "snow_3h": data.get("snow", {}).get("3h"),
    }


# ============================================================
# Forecast (Daily)
# ============================================================

@app.get("/forecast")
def get_forecast(city: str, units: str = "metric"):
    units = validate_units(units)
    lat, lon, name, _ = geocode_city(city)

    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"lat": lat, "lon": lon, "appid": API_KEY, "units": units}

    r = requests.get(url, params=params)
    if r.status_code != 200:
        raise HTTPException(500, "Forecast unavailable")

    data = r.json()

    daily = {}

    for entry in data["list"]:
        date = entry["dt_txt"].split(" ")[0]
        temp = entry["main"]["temp"]
        humidity = entry["main"]["humidity"]
        condition = entry["weather"][0]["description"]
        icon = entry["weather"][0]["icon"]

        rain = entry.get("rain", {}).get("3h", 0)
        snow = entry.get("snow", {}).get("3h", 0)
        precip = rain + snow

        if date not in daily:
            daily[date] = {
                "min_temp": temp,
                "max_temp": temp,
                "humidity": humidity,
                "condition": condition,
                "icon": icon,
                "precip_mm": precip,
            }
        else:
            daily[date]["min_temp"] = min(daily[date]["min_temp"], temp)
            daily[date]["max_temp"] = max(daily[date]["max_temp"], temp)
            daily[date]["precip_mm"] += precip

    result = []
    for d in list(daily.keys())[:5]:
        result.append(
            {
                "date": d,
                "min_temp": daily[d]["min_temp"],
                "max_temp": daily[d]["max_temp"],
                "humidity": daily[d]["humidity"],
                "condition": daily[d]["condition"],
                "icon": daily[d]["icon"],
                "precip_mm": round(daily[d]["precip_mm"], 2),
            }
        )

    return {"city": name, "daily": result}


# ============================================================
# Hourly Forecast
# ============================================================

@app.get("/hourly")
def get_hourly(city: str, units: str = "metric", hours: int = 12):
    units = validate_units(units)
    lat, lon, name, _ = geocode_city(city)

    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"lat": lat, "lon": lon, "appid": API_KEY, "units": units}

    r = requests.get(url, params=params)
    data = r.json()

    needed = math.ceil(hours / 3)
    timeline = []

    for entry in data["list"][:needed]:
        timeline.append(
            {
                "time": entry["dt_txt"],
                "temperature": entry["main"]["temp"],
                "feels_like": entry["main"]["feels_like"],
                "humidity": entry["main"]["humidity"],
                "condition": entry["weather"][0]["description"],
                "icon": entry["weather"][0]["icon"],
            }
        )

    return {"city": name, "timeline": timeline}


# ============================================================
# Map / Coordinates
# ============================================================

@app.get("/coords")
def coords(city: str):
    lat, lon, name, country = geocode_city(city)
    return {"city": name, "country": country, "lat": lat, "lon": lon}


# ============================================================
# UV Index (safe fallback)
# ============================================================

@app.get("/uv")
def get_uv(city: str, units: str = "metric"):
    units = validate_units(units)
    lat, lon, name, _ = geocode_city(city)

    data = one_call(lat, lon, units, exclude="hourly,daily,minutely")

    uvi = data.get("current", {}).get("uvi", 0)  # SAFE FALLBACK

    if uvi < 3:
        category = "Low"
    elif uvi < 6:
        category = "Moderate"
    elif uvi < 8:
        category = "High"
    elif uvi < 11:
        category = "Very High"
    else:
        category = "Extreme"

    return {"city": name, "uv_index": uvi, "uv_category": category}


# ============================================================
# AQI
# ============================================================

@app.get("/aqi")
def get_aqi(city: str):
    lat, lon, name, _ = geocode_city(city)

    url = "http://api.openweathermap.org/data/2.5/air_pollution"
    params = {"lat": lat, "lon": lon, "appid": API_KEY}

    r = requests.get(url, params=params)
    data = r.json()

    aqi = data["list"][0]["main"]["aqi"]

    category = {
        1: "Good",
        2: "Fair",
        3: "Moderate",
        4: "Poor",
        5: "Very Poor",
    }.get(aqi, "Unknown")

    return {"city": name, "aqi": aqi, "category": category}


# ============================================================
# Weather Alerts (SAFE fallback)
# ============================================================

@app.get("/alerts")
def get_alerts(city: str, units: str = "metric"):
    units = validate_units(units)
    lat, lon, name, _ = geocode_city(city)

    data = one_call(lat, lon, units, exclude="current,minutely,hourly,daily")

    alerts = data.get("alerts", [])

    # SAFE FALLBACK — no crash
    if not alerts:
        return {"city": name, "alerts": []}

    result = []
    for a in alerts:
        result.append(
            {
                "event": a.get("event", "No title"),
                "description": a.get("description", ""),
                "sender_name": a.get("sender_name", ""),
            }
        )

    return {"city": name, "alerts": result}


# ============================================================
# Outfit Recommendation
# ============================================================

@app.get("/outfit")
def outfit(city: str, units: str = "metric"):
    units = validate_units(units)
    weather = get_weather(city, units)
    uv = get_uv(city, units)

    temp = weather["temperature"]
    condition = weather["condition"]
    wind = weather["wind_speed"] or 0

    rain = (weather.get("rain_1h") or 0) + (weather.get("rain_3h") or 0)
    snow = (weather.get("snow_1h") or 0) + (weather.get("snow_3h") or 0)
    precip = rain + snow

    temp_c = temp if units == "metric" else (temp - 32) * 5 / 9

    clothing = []
    accessories = []
    notes = []

    # Temperature logic
    if temp_c <= 0:
        clothing.append("Heavy winter coat")
        accessories.append("Gloves, scarf, warm hat")
        notes.append("Very cold weather.")
    elif temp_c <= 10:
        clothing.append("Coat or thick jacket")
        notes.append("Cool temperatures.")
    elif temp_c <= 20:
        clothing.append("Light jacket or sweater")
    else:
        clothing.append("Light clothing")
        notes.append("Warm temperatures.")

    # Precipitation
    if rain > 0:
        accessories.append("Umbrella")
        notes.append("Rain expected.")
    if snow > 0:
        clothing.append("Snow boots")
        notes.append("Snowy conditions.")

    # UV
    if uv["uv_category"] in ("High", "Very High", "Extreme"):
        accessories.append("Sunscreen")
        notes.append(f"UV levels are {uv['uv_category'].lower()}.")

    summary = f"In {city}, it's {round(temp,1)}°{'C' if units=='metric' else 'F'} with {condition}."

    return {
        "city": city,
        "temperature": temp,
        "condition": condition,
        "precip_mm": round(precip, 2),
        "uv_category": uv["uv_category"],
        "summary": summary,
        "clothing": clothing,
        "accessories": accessories,
        "notes": notes,
    }


# ============================================================
# MULTI-CITY COMPARISON
# ============================================================

@app.get("/compare")
def compare(cities: str, units: str = "metric"):
    units = validate_units(units)
    names = [c.strip() for c in cities.split(",") if c.strip()]

    result = []

    for name in names:
        try:
            w = get_weather(name, units)
            aq = get_aqi(name)

            result.append(
                {
                    "city": w["city"],
                    "temperature": w["temperature"],
                    "condition": w["condition"],
                    "humidity": w["humidity"],
                    "wind_speed": w["wind_speed"],
                    "aqi": aq["aqi"],
                    "aqi_category": aq["category"],
                }
            )
        except:
            continue

    return {"cities": result}


# ============================================================
# (TRAVEL CHECKLIST REMOVED — COMMENTED OUT)
# ============================================================

"""
@app.get("/travel_checklist")
def travel_checklist(city: str, units: str = "metric"):
    # This feature is removed for now.
    return {"message": "Travel checklist disabled"}
"""
# ============================================================
# Reverse Geocoding (lat -> city)
# ============================================================

@app.get("/reverse_geocode")
def reverse_geocode(lat: float, lon: float):
    geo_url = "http://api.openweathermap.org/geo/1.0/reverse"
    params = {"lat": lat, "lon": lon, "limit": 1, "appid": API_KEY}

    resp = requests.get(geo_url, params=params)
    data = resp.json()

    # SAFE FALLBACKS to avoid undefined
    if resp.status_code != 200 or not data:
        return {"city": "Unknown"}

    city = (
        data[0].get("name")
        or data[0].get("state")
        or data[0].get("country")
        or "Unknown"
    )

    return {"city": city}

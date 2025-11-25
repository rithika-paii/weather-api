# Weather API (FastAPI)

This is the backend weather API powering the Weather Dashboard.  
It uses OpenWeatherMap APIs and exposes:

- /weather
- /forecast
- /hourly
- /coords
- /uv
- /aqi
- /alerts
- /outfit
- /compare

Travel checklist removed by design.

## 🚀 Deploy on Render

### 1. Create a new Web Service on Render
https://render.com

### 2. Choose your GitHub repo: `weather-backend`

### 3. Configure:
**Build Command**
pip install -r requirements.txt

**Start Command**
uvicorn main:app --host 0.0.0.0 --port $PORT

### 4. Deploy 🎉

You will get a URL like:
https://your-weather-api.onrender.com


Use this in your frontend.


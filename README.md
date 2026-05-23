Tokyo Weather API  
Markdown
# 🗼 Tokyo Weather & Rainfall Monitoring App

Welcome! This is a simple, lightweight web application and data tool that gives you a complete, up-to-the-minute look at the weather, air quality, and rainfall in Tokyo, Japan. 

It takes raw, messy numbers from global weather servers and organizes them into a clean, easy-to-read, visually beautiful dashboard complete with a live tracking map.

![FastAPI](https://img.shields.io/badge/Made%20With-FastAPI-005571?style=flat-square)
![Python](https://img.shields.io/badge/Language-Python-3670A0?style=flat-square)
![OpenWeatherMap](https://img.shields.io/badge/Data%20Source-OpenWeatherMap-EB6E4B?style=flat-square)

---

## 👀 What Does This App Do?

If you visit the dashboard, it instantly displays five key pieces of information on a single page:

1. **Current Conditions:** The exact temperature in Celsius, humidity levels, and wind speed/direction in Tokyo right now.
2. **Air Quality Tracker:** A colored health badge (Green for Good, Red for Poor) that breaks down common city air pollutants like carbon monoxide and smog particles.
3. **5-Day Outlook:** A quick, visual glance at what the weather looks like for the rest of the week.
4. **Rainfall Predictor:** A specialized table showing exactly how many millimeters of rain are expected to fall over the next few hours so you know when to grab an umbrella.
5. **Interactive Rain Map:** A live, zoomable map of Tokyo that displays real-time rain intensity clouds over the city.

---

## 📸 App Preview (What It Looks Like)

### The Main Dashboard
*(Replace this placeholder with a screenshot of your app's main page)*
![App Dashboard Snapshot](https://via.placeholder.com/1000x500/000000/FFFFFF?text=Tokyo+Weather+Dashboard+Screenshot)

### The Live Precipitation Radar
*(Replace this placeholder with a screenshot of your interactive map)*
![Interactive Map View](https://via.placeholder.com/1000x350/000000/FFFFFF?text=Live+Rain+Intensity+Radar+Map)

---

## 🧠 Smart Features Built Inside (Under the Hood)

Even though it looks simple on the outside, the application is designed to be highly efficient:
* **The 6-Hour Memory (Caching):** Instead of constantly bothering the weather servers every single time a user refreshes the page (which can cost money or get the app blocked), the app memorizes the weather for 6 hours. If someone refreshes the page, it instantly loads the memorized data.
* **Speed Optimization:** The code is bundled so that it grabs current weather, forecasts, and air quality all at the exact same time behind the scenes, making the page load incredibly fast.
* **Anti-Crash Protection (Rate Limiting):** If a rogue computer script tries to spam the website with thousands of requests a second, the app automatically blocks them to stay online for normal human visitors.

---

## 🛠️ Technical Setup (For Developers)

If you are a programmer and want to run this project on your own computer, follow these quick steps:

### 1. Requirements
Make sure you have Python 3.8 or higher installed. You will also need a free API Key from **OpenWeatherMap**.

### 2. Installation
Clone this repository, move into the directory, and install the required packages:
```bash
git clone [https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git](https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git)
cd YOUR_REPO_NAME
pip install fastapi slowapi pydantic requests pytz python-dotenv uvicorn
Real-time weather and air quality app. pertaining to the city of Tokyo, Japan.  
URL: https://tokyo-weather-api.vercel.app/rainfall/formatted


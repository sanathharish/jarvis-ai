import requests
from config import OPENWEATHER_API_KEY

def get_weather(city: str) -> str:
    url = f"http://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric"
    }
    response = requests.get(url, params=params)
    if response.status_code != 200:
        return f"Could not fetch weather for {city}."
    
    data = response.json()
    return (
        f"Weather in {city}: {data['weather'][0]['description']}, "
        f"Temperature: {data['main']['temp']}°C, "
        f"Feels like: {data['main']['feels_like']}°C, "
        f"Humidity: {data['main']['humidity']}%"
    )
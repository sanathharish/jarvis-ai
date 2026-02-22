import httpx
from config import OPENWEATHER_API_KEY

def get_weather(city: str) -> str:
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric"
    }
    response = httpx.get(url, params=params, timeout=5)
    if response.status_code != 200:
        return f"Could not fetch weather for {city}."
    
    data = response.json()
    return (
        f"Weather in {city}: {data['weather'][0]['description']}, "
        f"Temperature: {data['main']['temp']}°C, "
        f"Feels like: {data['main']['feels_like']}°C, "
        f"Humidity: {data['main']['humidity']}%"
    )

async def async_get_weather(city: str) -> dict:
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
    }
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()

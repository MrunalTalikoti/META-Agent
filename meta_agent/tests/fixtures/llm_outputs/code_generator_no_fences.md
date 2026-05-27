Here's the implementation:

def calculate_shipping(weight_kg: float, distance_km: float) -> float:
    base_rate = 5.0
    weight_rate = 0.5 * weight_kg
    distance_rate = 0.1 * distance_km
    return round(base_rate + weight_rate + distance_rate, 2)

This uses a simple linear model with base cost plus weight and distance surcharges.

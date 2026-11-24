"""Rule-based drought and water-stress assessment.

This is an initial transparent baseline, not a trained or validated ML model.
"""


def _get_value(day, *names):
    """Read a weather value from a ForecastDay object or dictionary."""
    for name in names:
        if isinstance(day, dict):
            value = day.get(name)
        else:
            value = getattr(day, name, None)

        if value is not None:
            return value

    return None


def assess_water_stress(forecast):
    """Estimate water stress from forecast rainfall and temperature."""

    if not forecast:
        return {
            "status": "unavailable",
            "risk": None,
            "message": "Weather forecast data is unavailable.",
        }

    rainfall_values = []
    temperature_values = []

    for day in forecast:
        rain = _get_value(
            day, "precipitation_mm", "precipitation", "rain_mm"
        )
        temperature = _get_value(
            day, "temperature_c", "temperature_2m", "temperature"
        )

        if rain is not None:
            rainfall_values.append(float(rain))

        if temperature is not None:
            temperature_values.append(float(temperature))

    if not rainfall_values or not temperature_values:
        return {
            "status": "unavailable",
            "risk": None,
            "message": "Required rainfall or temperature fields are missing.",
        }

    average_rainfall = sum(rainfall_values) / len(rainfall_values)
    average_temperature = (
        sum(temperature_values) / len(temperature_values)
    )

    score = 0

    if average_rainfall < 1:
        score += 60
    elif average_rainfall < 3:
        score += 40
    elif average_rainfall < 5:
        score += 20

    if average_temperature >= 35:
        score += 40
    elif average_temperature >= 30:
        score += 25
    elif average_temperature >= 25:
        score += 10

    score = min(score, 100)

    if score >= 70:
        risk = "high"
        message = "High potential water-stress risk."
    elif score >= 40:
        risk = "moderate"
        message = "Moderate potential water-stress risk."
    else:
        risk = "low"
        message = "Low potential water-stress risk."

    return {
        "status": "estimated",
        "risk": risk,
        "score": score,
        "average_rainfall_mm": round(average_rainfall, 2),
        "average_temperature_c": round(average_temperature, 2),
        "message": message,
        "method": "rule_based_baseline",
    }

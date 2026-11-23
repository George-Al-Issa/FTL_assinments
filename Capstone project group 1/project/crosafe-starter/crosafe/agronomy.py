"""Explicit demo crop rules and interfaces for validated yield models."""
from decimal import Decimal
from operator import ge, le
from typing import Protocol

from .contracts import ForecastDay

# Illustrative planning inputs. Replace these with reviewed regional parameters.
CROPS = {
    "wheat": {"en": "Wheat", "ar": "القمح", "demo_yield": "2.1", "check_days": 3,
              "info": ["Cool-season cereal. Scout for leaf rust and aphids.",
                       "حبوب موسم بارد. افحص الأوراق بحثاً عن الصدأ وحشرات المنّ."]},
    "barley": {"en": "Barley", "ar": "الشعير", "demo_yield": "1.8", "check_days": 4,
               "info": ["Cool-season cereal. Scout for leaf spots and aphids.",
                        "حبوب موسم بارد. راقب تبقّعات الأوراق وحشرات المنّ."]},
    "lentil": {"en": "Lentil", "ar": "العدس", "demo_yield": "1.0", "check_days": 4,
               "info": ["Pulse crop. Scout for wilt and inspect drainage.",
                        "محصول بقولي. راقب الذبول وافحص تصريف المياه."]},
    "chickpea": {"en": "Chickpea", "ar": "الحمّص", "demo_yield": "1.2", "check_days": 4,
                 "info": ["Pulse crop. Scout for blight and pod damage.",
                          "محصول بقولي. راقب اللفحة وأضرار القرون."]},
}


class YieldModel(Protocol):
    source: str

    def tonnes(self, crop: str, field: dict) -> Decimal: ...


class DemoYieldModel:
    source = "demo-v1"

    def tonnes(self, crop: str, field: dict) -> Decimal:
        return (Decimal(CROPS[crop]["demo_yield"]) * Decimal(str(field["area_ha"]))).quantize(
            Decimal("0.001")
        )


GUIDANCE = {
    "heat": ["Check soil moisture early and review irrigation with local extension.",
             "افحص رطوبة التربة صباحاً وراجع خطة الري مع الإرشاد الزراعي."],
    "frost": ["Check local frost advisories and monitor vulnerable seedlings.",
              "تابع تنبيهات الصقيع المحلية وراقب الشتلات الحساسة."],
    "heavy_rain": ["Check drainage and review any planned irrigation.",
                   "افحص المصارف وراجع أي ريّ مخطّط."],
    "dry_spell": ["Monitor root-zone moisture and review water availability.",
                  "راقب رطوبة منطقة الجذور وتحقق من توفر مياه الري."],
}


def forecast_events(days: list[ForecastDay], thresholds: dict) -> list[dict]:
    events = []
    dry_run = []
    for day in sorted(days, key=lambda item: item.day):
        readings = (
            ("heat", day.max_temperature_c, thresholds["heat_c"], ge),
            ("frost", day.min_temperature_c, thresholds["frost_c"], le),
            ("heavy_rain", day.precipitation_mm, thresholds["rain_mm"], ge),
        )
        for kind, value, threshold, compare in readings:
            if value is not None and compare(value, threshold):
                events.append({"kind": kind, "start": day.day, "end": day.day,
                               "guidance": GUIDANCE[kind]})
        if dry_run and (day.day - dry_run[-1]).days != 1:
            dry_run.clear()
        if day.precipitation_mm is None or day.precipitation_mm > thresholds["dry_mm"]:
            dry_run.clear()
        else:
            dry_run.append(day.day)
            if len(dry_run) == thresholds["dry_days"]:
                events.append({"kind": "dry_spell", "start": dry_run[0], "end": dry_run[-1],
                               "guidance": GUIDANCE["dry_spell"]})
    return events

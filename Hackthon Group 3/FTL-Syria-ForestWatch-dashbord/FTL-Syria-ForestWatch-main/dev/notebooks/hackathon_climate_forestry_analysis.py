import pandas as pd
from scipy.stats import pearsonr, linregress

# Load the three source datasets
fa = pd.read_csv("FAOSTAT_data_en_9-28-2026.csv")
nasa = pd.read_csv("POWERPointMonthly2000...ELST.csv", skiprows=10)
cru = "cru_x0_5_timeseries_tasmax,tas,pr_timeseries_annual_1901_2025_mean.xlsx"

# 1) FAOSTAT: use the two wood-fuel production series
fa = fa[fa["Year"].between(2000, 2024)]
wood_items = ["Wood fuel, coniferous", "Wood fuel, non-coniferous"]
wood = fa[fa["Item"].isin(wood_items)].groupby("Year")["Value"].sum()

# 2) NASA POWER: annual solar radiation and 10-m wind speed
solar = nasa[nasa.PARAMETER == "ALLSKY_SFC_SW_DWN"].set_index("YEAR")["ANN"]
wind = nasa[nasa.PARAMETER == "WS10M"].set_index("YEAR")["ANN"]

# 3) CRU: annual precipitation, mean temperature and maximum temperature
cru_data = {}
for var in ["pr", "tas", "tasmax"]:
    d = pd.read_excel(cru, sheet_name=var)
    row = d.iloc[0]
    cru_data[var] = pd.Series(
        {int(str(c)[:4]): row[c] for c in d.columns
         if str(c)[:4].isdigit() and 2000 <= int(str(c)[:4]) <= 2024}
    )

data = pd.concat([wood.rename("wood_fuel_m3"),
                  solar.rename("solar_kwh_m2_day"),
                  wind.rename("wind_10m_ms"),
                  cru_data["pr"].rename("precipitation_mm"),
                  cru_data["tas"].rename("tas_c"),
                  cru_data["tasmax"].rename("tasmax_c")], axis=1).dropna()

# Analysis 1: production trend
slope, intercept, r, p, se = linregress(data.index, data["wood_fuel_m3"])
print("Wood-fuel trend:", slope, "m3/year; p =", p)

# Analysis 2: Pearson correlations
for col in ["precipitation_mm", "tas_c", "tasmax_c",
            "solar_kwh_m2_day", "wind_10m_ms"]:
    r, p = pearsonr(data["wood_fuel_m3"], data[col])
    print(col, "r =", round(r, 3), "p =", round(p, 4))

# Analysis 3: remove the linear time trend before correlation
def detrend(s):
    sl, itc, *_ = linregress(data.index, s)
    return s - (itc + sl * data.index)

for col in ["precipitation_mm", "tas_c", "tasmax_c",
            "solar_kwh_m2_day", "wind_10m_ms"]:
    r, p = pearsonr(detrend(data["wood_fuel_m3"]), detrend(data[col]))
    print("Detrended", col, "r =", round(r, 3), "p =", round(p, 4))

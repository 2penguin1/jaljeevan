# Seed data sources

Downloaded, not committed. Git ignores everything here except this README.

| File | Source | Notes |
|---|---|---|
| `india_district.geojson` | https://github.com/geohacker/india/raw/master/district/india_district.geojson | properties `NAME_1` = state, `NAME_2` = district |
| `IN.txt` | unzip https://download.geonames.org/export/dump/IN.zip | every populated place in India, with coordinates and population (CC-BY 4.0, GeoNames) |
| `admin1CodesASCII.txt` | https://download.geonames.org/export/dump/admin1CodesASCII.txt | maps `IN.24` → Rajasthan |
| `bbmp_wards.geojson` | https://github.com/datameet/Municipal_Spatial_Data/raw/master/Bangalore/BBMP.geojson | Bengaluru ward polygons; pass the ward-name property via `--ward-name-prop` |
| `district_population.csv` (optional) | Census 2011 district table, columns `state,district,population` | if missing, district population is the sum of its towns and villages |
| `imd_rainfall_2026.csv` (optional) | IMD district rainfall for the 2026 monsoon, columns `state_code,district,period,rainfall_departure_pct` | compiled by hand |

Load with: `cd backend && uv run python -m app.cli.seed_geo`

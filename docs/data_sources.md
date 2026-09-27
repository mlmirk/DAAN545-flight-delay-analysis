# Data sources

## 1. BTS Airline Delay Cause (primary)

- **What:** Monthly arrival delay counts and delay minutes by cause, at the grain **carrier × airport × year × month**.
- **Local file:** `data/raw/Airline_Delay_Cause.csv`
- **Definitions:** `data/raw/Download_Column_Definitions.xlsx`
- **Publisher:** U.S. Bureau of Transportation Statistics (BTS)

Cleaning for this table is implemented in `src/cleaning.py` (`clean_delay_cause`): coerce numerics, drop duplicate keys, fill structural `arr_del15` nulls when there are no arrivals, and add rate features.

## 2. OpenFlights airport database (reference / join)

- **What:** Worldwide airport reference (IATA/ICAO, city, country, lat/lon, altitude, timezone).
- **Local file:** `data/raw/airports.dat`
- **Upstream:** [OpenFlights `airports.dat`](https://github.com/jpatokal/openflights/blob/master/data/airports.dat)
- **Format:** CSV with **no header**; missing values encoded as `\N`

### What we clean before joining

Implemented in `load_openflights_airports` / `join_airport_attributes`:

1. Assign the official OpenFlights column names
2. Convert `\N` sentinels to null
3. Drop airports with no IATA code (cannot match BTS `airport`)
4. Uppercase / strip IATA codes; keep one row per IATA
5. Coerce `lat`, `lon`, `altitude_ft`, `timezone_offset` to numeric
6. Restrict the lookup to IATA codes present in the delay extract (keeps grain monthly; no row explosion)
7. Parse `state` from BTS `airport_name` (`City, ST: …`) and map `census_region`
8. Map OpenFlights `tz` → `tz_group` (Eastern / Central / Mountain / Pacific / …)

### Join key and match reporting

- **Key:** BTS `airport` = OpenFlights `iata` (e.g. `ATL`, `ORD`)
- The notebook prints airport-level and row-level **matched vs lost** counts for the P1 integration writeup

## 3. Association-rule binary matrix (derived)

- **Built from:** `data/processed/airline_delay_cause_with_airports.csv`
- **Code:** `src/association_rules.py` → `build_transaction_matrix`
- **Notebook:** `notebooks/02_association_rules.ipynb`
- **Exports:** `association_binary_matrix.csv`, `association_rules_min_support_0_05.csv`

Binary items include discretized delay/cancel rates, cause-dominance flags, season, census region / timezone one-hots, altitude/latitude flags, and top carrier/airport indicators for mlxtend `apriori` / `fpgrowth` / `association_rules`.

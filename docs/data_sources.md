# Data sources

Catalog of every external and derived dataset used for this project.
Update this file whenever someone adds a new pull.

Plain-language definitions of columns and methods: [`glossary.md`](glossary.md).

---

## In the repo now

### 1. BTS Airline Delay Cause (primary panel)

| | |
|---|---|
| **What** | Monthly arrival delay counts and delay minutes by cause |
| **Grain** | carrier × airport × year × month |
| **Local** | `data/raw/Airline_Delay_Cause.csv` |
| **Definitions** | `data/raw/Download_Column_Definitions.xlsx` |
| **Publisher** | [U.S. Bureau of Transportation Statistics (BTS)](https://www.transtats.bts.gov/) |
| **Code** | `src/cleaning.py` → `load_delay_cause`, `clean_delay_cause` |
| **Notebook** | `notebooks/01_eda_clean_visualize.ipynb` |

**Cleaning summary:** normalize column names, coerce numerics, drop duplicate keys, fill structural `arr_del15` nulls when `arr_flights == 0`, add rate features (`pct_delayed`, etc.).

---

### 2. OpenFlights airport database (geo join)

| | |
|---|---|
| **What** | Worldwide airport reference: IATA/ICAO, city, country, lat/lon, altitude, timezone |
| **Grain** | one row per airport (we keep only codes in our delay extract) |
| **Local** | `data/raw/airports.dat` |
| **Upstream** | [OpenFlights `airports.dat`](https://github.com/jpatokal/openflights/blob/master/data/airports.dat) |
| **Format** | CSV, **no header**; missing values as `\N` |
| **Code** | `src/cleaning.py` → `load_openflights_airports`, `join_airport_attributes` |
| **Join key** | BTS `airport` = OpenFlights `iata` |

**Cleaning summary:** name columns, `\N` → null, drop missing IATA, uppercase codes, one row per IATA, numeric lat/lon/altitude, parse `state` from BTS name, map `census_region` and `tz_group`.

**Match (this extract):** 30/30 airports, 8,963/8,963 rows (100%).

---

### 3. Airport hub / ops profile (static airport join)

| | |
|---|---|
| **What** | Hub size, CY2023 enplanements, slot-controlled flag, open runway count |
| **Grain** | one row per airport |
| **Local** | `data/raw/airport_hub_profile.csv` |
| **Rebuild** | `scripts/build_airport_hub_profile.py` |
| **Code** | `src/cleaning.py` → `load_airport_hub_profile`, `join_hub_profile` |
| **Join key** | BTS `airport` |
| **Notebook** | `notebooks/01_eda_clean_visualize.ipynb` §4b |

| Field | Upstream source |
|---|---|
| `hub_size`, `hub_code`, `enplanements_cy23` | [FAA CY2023 commercial service enplanements](https://www.faa.gov/airports/planning_capacity/passenger_allcargo_stats/passenger/cy23_commercial_service_enplanements) ([Excel](https://www.faa.gov/sites/faa.gov/files/2024-10/cy23-commercial-service-enplanements.xlsx)); category defs: [FAA airport categories](https://www.faa.gov/airports/planning_capacity/categories) |
| `slot_controlled` | FAA slot-controlled airports: **JFK, LGA, EWR, DCA** |
| `runway_count` | [OurAirports `runways.csv`](https://davidmegginson.github.io/ourairports-data/runways.csv) (+ [airports.csv](https://davidmegginson.github.io/ourairports-data/airports.csv) for IATA→ident); counts **open** runways (`closed == 0`) |

**Match (this extract):** 30/30 airports. In CY2023 FAA data all 30 are **Large** hubs; useful variation is `slot_controlled`, `runway_count`, and `enplanements_cy23`.

---

### 4. Airport staffing (static airport join)

| | |
|---|---|
| **What** | Current controller staffing, workforce target, training time, training success, and facility level |
| **Grain** | one row per airport |
| **Local** | `data/raw/airport_staffing.csv` |
| **Code** | `src/cleaning.py` → `load_airport_staffing`, `join_airport_staffing` |
| **Join key** | BTS `airport` |
| **Notebook** | `notebooks/01_eda_clean_visualize.ipynb` §4c |

| Field | Meaning in this file |
|---|---|
| `cur_staff_pct` | Current staff as a percent of target (can exceed 100) |
| `crwg_target` | Target staffing level (`CRWGTarget`) |
| `training_time_yrs` | Training time, in years |
| `training_success_pct` | Training success rate, percent |
| `facility_level` | Facility complexity level (integer) |

Percents are stored as numbers on a 0–100 scale (`75%` → `75`).

**Match (this extract):** 30/30 delay airports and 8,963/8,963 rows (100%). The staffing file also includes **HNL, RDU, and STL**, which are not in the delay extract, so those three rows do not attach to any delay record.

---

### 5. Association-rule binary matrix (derived — not a new download)

| | |
|---|---|
| **Built from** | `data/processed/airline_delay_cause_with_airports.csv` |
| **Local exports** | `data/processed/association_binary_matrix.csv`, `association_rules_min_support_0_05.csv` |
| **Code** | `src/association_rules.py` → `build_transaction_matrix` |
| **Notebook** | `notebooks/02_association_rules.ipynb` |
| **Library** | [mlxtend](https://github.com/rasbt/mlxtend) (`apriori`, `fpgrowth`, `association_rules`) |

Binary items include discretized delay/cancel rates, cause-dominance flags, season, region/timezone one-hots, altitude/latitude flags, hub/slot/runway flags (when present), and top carriers/airports.

---

## Processed outputs (what analysis reads)

| File | Description |
|---|---|
| `data/processed/airline_delay_cause_clean.csv` | Cleaned BTS panel + derived rates |
| `data/processed/airline_delay_cause_with_airports.csv` | Above + OpenFlights geo + hub/ops + staffing fields |
| `data/processed/association_binary_matrix.csv` | 0/1 item matrix for ARM |
| `data/processed/association_rules_min_support_0_05.csv` | Exported rules (delay-related filter) |

---

## How to add a new source

1. Save raw file under `data/raw/` (prefer small extracts; see `.gitignore` for allowed extensions).
2. Add a section to **this file**: what / grain / URL / local path / join key / cleaning notes.
3. Put load/join helpers in `src/` and call them from a notebook.
4. Report **matched vs lost** row/key counts in the notebook for the P1 writeup.

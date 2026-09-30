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

### 4. FAA airport staffing (static airport file)

| | |
|---|---|
| **What** | Air traffic controller staffing snapshot: current staff vs. target, training time, training success, and facility level |
| **Grain** | one row per airport (not monthly; does not vary by carrier or year) |
| **Local** | `data/raw/airport_staffing.csv` (saved from `Airport Staffing Data.csv`) |
| **Publisher** | [Federal Aviation Administration (FAA)](https://www.faa.gov/) air traffic controller staffing |
| **Upstream** | [FAA Air Traffic Controller Workforce Plan](https://www.faa.gov/about/office_org/headquarters_offices/afn/offices/finance/offices/office-financial-labor-analysis/plans/controller-workforce) ([FY2025–2028 PDF](https://www.faa.gov/sites/faa.gov/files/fy25-air-traffic-controller-workforce-plan_0.pdf)); CRWG definition and comparison: [National Academies review of ATC staffing models](https://www.nationalacademies.org/read/29112/chapter/6) |
| **Format** | CSV with a header. Percents include a `%` sign (`75%`, `85.88%`). Training time is text ending in `yrs` (`1.03 yrs`). The `CurStaff` header has a trailing space in the raw file. |
| **Code** | `src/cleaning.py` → `load_airport_staffing` (reads this file only; does not attach it to the delay panel) |
| **Kept separate** | Not merged into `data/processed/airline_delay_cause_with_airports.csv`. Both files use IATA airport codes if a later analysis joins them. |

| Raw column | Cleaned name | Upstream meaning |
|---|---|---|
| `Airport` | `airport` | IATA code of the ATC facility’s airport |
| `CurStaff` | `cur_staff_pct` | Controllers currently on board as a **percent of the CRWG target**. Can exceed 100 when the facility is above target. |
| `CRWGTarget` | `crwg_target` | **Collaborative Resource Workgroup** target: the number of Certified Professional Controllers (CPCs) the FAA/NATCA model says the facility should have. CPCs only — trainees do not count toward this target. |
| `TrainingTime` | `training_time_yrs` | Time to complete facility training, in years |
| `TrainingSuccess` | `training_success_pct` | Share of trainees who successfully certify, percent |
| `FacilityLevel` | `facility_level` | FAA ATC **facility level** (complexity / pay level). Higher number = more traffic and more complex airspace. Terminal facilities are typically 4–12; **12 is the highest**. |

**Cleaning summary:** strip header spaces, uppercase IATA codes, drop duplicate airports, turn percents into 0–100 numbers (`75%` → `75`), and turn training time into a number of years (`1.03 yrs` → `1.03`).

**This extract:** 33 airports. The delay panel’s 30 airports are all in this file, plus **HNL, RDU, and STL**. The staffing file stays separate from the BTS delay table.

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
| `data/processed/airline_delay_cause_with_airports.csv` | Above + OpenFlights geo + hub/ops fields |
| `data/processed/association_binary_matrix.csv` | 0/1 item matrix for ARM |
| `data/processed/association_rules_min_support_0_05.csv` | Exported rules (delay-related filter) |

---

## How to add a new source

1. Save raw file under `data/raw/` (prefer small extracts; see `.gitignore` for allowed extensions).
2. Add a section to **this file**: what / grain / URL / local path / join key / cleaning notes.
3. Put load/join helpers in `src/` and call them from a notebook.
4. Report **matched vs lost** row/key counts in the notebook for the P1 writeup.

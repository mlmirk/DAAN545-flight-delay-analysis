# Glossary

Plain-language definitions for columns, joins, and analysis terms used in this project.
Use this when writing the report or reading notebooks. Field names in backticks match the data.

Related: [`data_sources.md`](data_sources.md) (where data comes from).

---

## Data grain & IDs

| Term | Meaning |
|------|---------|
| **Grain / row** | One row = one **carrier × airport × year × month** (not individual flights). |
| **Carrier** | Airline code (e.g. `DL`, `AA`) and name (`carrier_name`). |
| **Airport / IATA** | Three-letter code (`ATL`, `ORD`). Join key to OpenFlights and hub profile. |
| **Period** | First day of the month (`year` + `month`) for time plots. |
| **Panel / extract** | Our analysis table built from BTS + joins (see `data/processed/`). |

---

## BTS delay measures

| Term / column | Meaning |
|---------------|---------|
| **Arrival** | Flight counted at the destination airport in BTS reporting. |
| **`arr_flights`** | Number of arriving flights in that carrier–airport–month. |
| **Delayed 15+ min / `arr_del15`** | Arrivals delayed **15 minutes or more** past schedule (BTS on-time definition). |
| **`pct_delayed`** | `100 × arr_del15 / arr_flights` — share of arrivals delayed 15+ min. |
| **`arr_cancelled` / `pct_cancelled`** | Cancellations and their share of scheduled arrivals. |
| **`arr_diverted`** | Arrivals diverted to another airport. |
| **`arr_delay`** | Total **minutes** of arrival delay (summed), not a count of flights. |
| **`avg_delay_min_per_delayed`** | Average delay minutes among delayed arrivals (`arr_delay / arr_del15`). |

### Delay **causes** (BTS attribution)

BTS splits delay into causes. Each has a **count** (`*_ct`, can be fractional) and **minutes** (`*_delay`).

| Cause | Columns | Plain meaning |
|-------|---------|----------------|
| **Carrier** | `carrier_ct`, `carrier_delay` | Airline-controlled (crew, maintenance, etc.). |
| **Weather** | `weather_ct`, `weather_delay` | Extreme weather (not routine ATC weather, which often falls under NAS). |
| **NAS** | `nas_ct`, `nas_delay` | National Airspace System — air traffic control, airport ops, non-extreme weather volume, etc. |
| **Security** | `security_ct`, `security_delay` | Security-related holds. |
| **Late aircraft** | `late_aircraft_ct`, `late_aircraft_delay` | Aircraft arrived late from previous flight (cascade). |

**Cause share:** that cause’s delay minutes ÷ total `arr_delay` (used for “dominant cause” flags).

---

## Geography & airport attributes

| Term / column | Meaning |
|---------------|---------|
| **OpenFlights** | External airport reference (lat/lon, altitude, timezone). |
| **`lat` / `lon`** | Airport latitude / longitude. |
| **`altitude_ft`** | Airport elevation in feet. |
| **`tz` / `tz_group`** | Timezone name and coarse group (Eastern, Central, Mountain, Pacific). |
| **`state`** | U.S. state/DC parsed from BTS `airport_name`. |
| **`census_region`** | Northeast / Midwest / South / West (from state). |
| **Hub size** | FAA category from passenger boardings: Large / Medium / Small / Nonhub. Our 30 airports are all **Large** in CY2023. |
| **`enplanements_cy23`** | FAA count of passengers boarded at the airport in calendar year 2023 (airport size). |
| **Slot-controlled** | Airports with FAA slot/scheduling limits: **JFK, LGA, EWR, DCA**. Congestion is tightly managed. |
| **`runway_count`** | Number of **open** runways (OurAirports). |
| **`cur_staff_pct`** | Current airport staff as a percent of the staffing target. Can be above 100. |
| **`crwg_target`** | Target staffing level from the staffing file (`CRWGTarget`). |
| **`training_time_yrs`** | Training time in years. |
| **`training_success_pct`** | Training success rate, percent. |
| **`facility_level`** | Facility complexity level (integer; higher is more complex). |
| **Match rate** | Share of airports/rows that successfully joined to a reference table (report this for integration). |

---

## Cleaning & stats (EDA)

| Term | Meaning |
|------|---------|
| **Missingness** | How often a column is null; we ask *why* and how we handle it. |
| **Structural zero / null** | Missing because there is nothing to measure (e.g. no arrivals → no delays). |
| **Duplicate key** | Same carrier–airport–year–month appearing more than once. |
| **IQR outlier** | Value outside Q1−1.5×IQR or Q3+1.5×IQR (Tukey rule). We **flag**, not auto-delete. |
| **Skew / kurtosis** | Shape of a distribution (asymmetric / heavy tails). Delay minutes are often right-skewed. |
| **Arrival-weighted** | Aggregate that weights by `arr_flights` so busy airports count more than quiet ones. |
| **Normalization / scaling** | Rescaling numbers (e.g. log, z-score, min–max) so features are comparable — still a light/optional step for us. |
| **Discretize** | Turn a continuous number into True/False with a cutoff (e.g. “above 75th percentile”). |
| **One-hot / dummy** | Turn a category into several 0/1 columns (e.g. `region_West`). |

---

## Association rule mining (ARM)

Used in `notebooks/02_association_rules.ipynb` with **mlxtend**.

| Term | Meaning |
|------|---------|
| **Transaction / basket** | One row of the binary matrix (one carrier–airport–month). |
| **Item** | A binary feature that is True for that row (e.g. `high_delay`, `is_summer`). |
| **Binary / item matrix** | Table of 0/1 columns ready for mining. |
| **`high_delay`** | `pct_delayed` at or above the 75th percentile (cutoff printed in the notebook). |
| **`*_dominant`** | That cause’s share of delay minutes ≥ ~35% (e.g. `weather_dominant`). |
| **Support** | Fraction of rows where an itemset appears. Higher = more common. |
| **`min_support`** | Threshold; raise it → fewer, more common patterns. |
| **Frequent itemset** | Set of items that meet `min_support`. |
| **Apriori / FP-Growth** | Two algorithms that find frequent itemsets (same results on our boolean data; FP-Growth is often faster). |
| **Association rule** | “If A, then B” (`antecedents` → `consequents`). |
| **Confidence** | Among rows with A, how often B also appears. |
| **Lift** | How much more often A and B occur together than if independent. **Lift > 1** = positive association. |
| **Antecedent / consequent** | Left / right side of a rule (“if” / “then”). |

---

## Plot & report language

| Phrase on figures | Meaning |
|-------------------|---------|
| **Share of arrivals delayed 15+ min (%)** | Same as `pct_delayed`. |
| **NAS (air traffic)** | National Airspace System delay minutes. |
| **Slot-controlled** | JFK / LGA / EWR / DCA. |
| **Annual passengers boarded, 2023** | FAA enplanements (airport size). |

---

## File cheat sheet

| Path | What it is |
|------|------------|
| `data/raw/Airline_Delay_Cause.csv` | Raw BTS panel |
| `data/raw/airports.dat` | OpenFlights airports |
| `data/raw/airport_hub_profile.csv` | Hub size, slots, runways |
| `data/raw/airport_staffing.csv` | Staffing, training, facility level |
| `data/processed/airline_delay_cause_with_airports.csv` | Main analysis table |
| `data/processed/association_binary_matrix.csv` | ARM 0/1 matrix |
| `reports/figures/` | Saved charts for the report |
| `notebooks/01_eda_clean_visualize.ipynb` | Cleaning, joins, EDA plots |
| `notebooks/02_association_rules.ipynb` | Binary encoding + rules |

---

## Acronyms

| Acronym | Expansion |
|---------|-----------|
| **BTS** | Bureau of Transportation Statistics |
| **FAA** | Federal Aviation Administration |
| **IATA** | Airport/airline code standard (3-letter airports) |
| **NAS** | National Airspace System (delay cause) |
| **ARM** | Association rule mining |
| **EDA** | Exploratory data analysis |
| **IQR** | Interquartile range |
| **CY** | Calendar year (e.g. CY2023) |

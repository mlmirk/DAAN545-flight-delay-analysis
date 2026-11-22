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
| **Airport / IATA** | Three-letter code (`ATL`, `ORD`). Join key to OpenFlights and the hub profile. The FAA staffing file uses the same codes but is kept as its own table. |
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
| **Match rate** | Share of airports/rows that successfully joined to a reference table (report this for integration). |

---

## FAA controller staffing

From `data/raw/airport_staffing.csv`. One static row per airport (see [`data_sources.md`](data_sources.md)). These fields describe the **air traffic control facility**, not the airlines.

| Term / column | Meaning |
|---------------|---------|
| **CPC** | **Certified Professional Controller** — a controller fully certified to work the positions at that facility. |
| **CRWG** | **Collaborative Resource Workgroup.** A joint FAA Air Traffic Organization and NATCA (controllers’ union) model that sets how many CPCs each facility should have. It counts **only CPCs**. Controllers still in training are not included. The FAA’s older staffing standard (AFN) is different: it also counts some previously certified controllers who are retraining (CPC-ITs). |
| **`crwg_target`** | That CRWG headcount target for the airport’s facility (`CRWGTarget` in the raw file). Example: a target of 52 means the model calls for 52 CPCs at that facility. |
| **`cur_staff_pct`** | Controllers currently on board as a percent of `crwg_target`. **100** means the facility is at target. **Above 100** means more CPCs than the target (MSP is 106; STL is 147). **Below 100** means short of the target (AUS is about 54). |
| **`training_time_yrs`** | How long facility training takes, in years. |
| **`training_success_pct`** | Percent of trainees who successfully finish certification. |
| **Facility level / `facility_level`** | FAA **ATC facility level**, an integer that ranks how busy and complex the facility is. It is also the controller **pay level**: a higher level pays more because the traffic is heavier and harder to work. Terminal facilities (towers and approach controls) usually run from **4 through 12**. **12 is the most complex** (in this file: ATL, DEN, DFW, ORD, CLT, MIA, PHL). The lowest level in this extract is **7** (STL). |

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

## Clustering

Used in `notebooks/03_clustering.ipynb`. Longer write-up: [`notebook_notes.md`](notebook_notes.md).

| Term | Meaning |
|------|---------|
| **Cluster** | A group of carrier–airport–months with a similar delay profile. |
| **K-Means** | Splits rows into k groups around centroids. Every row is assigned. |
| **Ward** | Hierarchical clustering. Merges groups so within-group variance stays small. We cut the tree at the same k as K-Means. |
| **Silhouette** | How well a row sits in its own cluster versus the next closest one. Higher is tighter. We pick k from the K-Means silhouette. Around 0.25 on this data means the groups overlap. |
| **Adjusted Rand index** | How much two labelings agree, adjusted for chance. 1 = same groups. Our K-Means vs Ward value is about 0.60. |
| **PCA** | Compresses scaled features into fewer components. We plot the first two. We only cluster in that plane if they explain at least 70% of the variance. Here they explain about 53%, so clustering stays in the original scaled features. |
| **Cause share** | That cause’s delay minutes ÷ `arr_delay`. Used as cluster features. |

---

## Outlier detection

Used in `notebooks/04_outlier_detection.ipynb`. Longer write-up: [`notebook_notes.md`](notebook_notes.md). Same months and same six profile features as clustering. We **flag**. We do not delete.

| Term | Meaning |
|------|---------|
| **Outlier (this project)** | A carrier–airport–month whose delay rate is extreme, or whose scaled delay profile is isolated from other months, or both. A bad month that looks like many other bad months is not automatically an outlier. |
| **IQR rates** | Tukey fence on `pct_delayed` or on `pct_cancelled` (Q1 − 1.5×IQR, Q3 + 1.5×IQR), computed on the scored months. On this extract both lower fences are below 0, so only the upper tail is flagged. |
| **k-NN distance** | Mean Euclidean distance to the 15 nearest other months in the scaled profile. Flagged when that distance is above its own upper Tukey fence. |
| **Isolation forest** | Tree model that isolates unusual rows. We flag `decision_function` < 0 with `contamination=0.05` (about 5% of months) and `random_state=42`. |
| **Consensus outlier** | Flagged by at least two of the three methods. |
| **Rate only** | IQR flag, and neither distance method. Usually a high cancellation rate with an ordinary cause mix. |
| **Shape only** | k-NN or the forest, and not IQR. Usually an unusual cause mix (often weather-heavy) at an ordinary delay rate. |
| **Rate and shape** | IQR and at least one distance method. High rates and an isolated profile together. |
| **Outlier removal** | Refitting K-Means and Ward after dropping flagged months. Notebook 05. The published fit keeps every month. Dropping consensus outliers softens the cancellation and weather groups. Dropping every flag takes the winter cancellation pattern out. |

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
| `data/raw/airport_staffing.csv` | FAA controller staffing (CRWG target, training, facility level) |
| `data/processed/airline_delay_cause_with_airports.csv` | Main analysis table |
| `data/processed/association_binary_matrix.csv` | ARM 0/1 matrix |
| `reports/figures/` | Saved charts for the report |
| `notebooks/01_eda_clean_visualize.ipynb` | Cleaning, joins, EDA plots |
| `notebooks/02_association_rules.ipynb` | Binary encoding + rules |
| `notebooks/03_clustering.ipynb` | K-Means and Ward clustering |
| `notebooks/04_outlier_detection.ipynb` | IQR, k-NN, and isolation forest flags |
| `notebooks/05_outlier_clustering_impact.ipynb` | Clustering with outliers kept vs removed |
| `data/processed/outlier_scores.csv` | Per-month outlier scores and flags |
| `docs/notebook_notes.md` | Write-up notes (not submitted as the notebook) |

---

## Acronyms

| Acronym | Expansion |
|---------|-----------|
| **BTS** | Bureau of Transportation Statistics |
| **FAA** | Federal Aviation Administration |
| **CRWG** | Collaborative Resource Workgroup (FAA/NATCA controller staffing targets) |
| **CPC** | Certified Professional Controller |
| **NATCA** | National Air Traffic Controllers Association |
| **IATA** | Airport/airline code standard (3-letter airports) |
| **NAS** | National Airspace System (delay cause) |
| **ARM** | Association rule mining |
| **EDA** | Exploratory data analysis |
| **IQR** | Interquartile range |
| **CY** | Calendar year (e.g. CY2023) |
| **PCA** | Principal component analysis |

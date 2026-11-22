# Notebook notes (not for submission)

Draft findings and reproducibility checklists moved out of the Jupyter notebooks so submission notebooks stay analysis-only. Use this file when writing the report or verifying a local run.

---

## From `01_eda_clean_visualize.ipynb`

### Brief findings (draft)

## 7. Brief findings (draft notes)

Use these bullets as a starting point for a written report — expand in your own words.

Last captured notebook output:

```text
=== Draft insights (edit for your report) ===

1. Panel covers 2024-06 → 2026-06 for 21 carriers and 30 airports (8,963 carrier-airport-months).
2. Data quality: 1 null cell(s) in raw; 0 duplicate key rows; after cleaning remaining nulls = 195.
3. Peak system delay month: 2024-07 at 28.4% delayed.
4. Delay-minute cause shares:
   - late_aircraft_delay: 38.7%
   - carrier_delay: 32.5%
   - nas_delay: 22.9%
   - weather_delay: 5.8%
   - security_delay: 0.1%
5. Highest airport delay rates (arrival-weighted):
   - SFO (San Francisco, CA: San Francisco International): 26.4%
   - DCA (Washington, DC: Ronald Reagan Washington National): 25.5%
   - FLL (Fort Lauderdale, FL: Fort Lauderdale-Hollywood International): 24.9%
6. OpenFlights airport join: 30/30 airports matched (100.0%); 8,963/8,963 rows (100.0%). Source: https://github.com/jpatokal/openflights/blob/master/data/airports.dat
7. Location vs delay (airport-level Spearman): lat-pct_delayed rho=-0.14, lon-pct_delayed rho=0.22, altitude-pct_delayed rho=-0.64.
8. Delay-rate distribution is right-skewed with high-volume hubs pulling long tails — IQR outliers are expected; treat as flags, not automatic deletes.
```

To regenerate those bullets, re-run the EDA notebook through section 6, then use this snippet:

```python
top_airports = (
    clean.groupby(["airport", "airport_name"], as_index=False)
    .agg(arr_flights=("arr_flights", "sum"), arr_del15=("arr_del15", "sum"))
)
top_airports["pct_delayed"] = 100 * top_airports["arr_del15"] / top_airports["arr_flights"]
top_airports = top_airports.sort_values("pct_delayed", ascending=False)

cause_share = 100 * clean[CAUSE_DELAY_COLS].sum() / clean[CAUSE_DELAY_COLS].sum().sum()
peak_month = monthly.loc[monthly["pct_delayed"].idxmax()]

print("=== Draft insights (edit for your report) ===\n")
print(f"1. Panel covers {overview['date_span']} for "
      f"{overview['n_carriers']} carriers and {overview['n_airports']} airports "
      f"({overview['n_rows']:,} carrier-airport-months).")
print(f"2. Data quality: {overview['total_nulls']} null cell(s) in raw; "
      f"{overview['duplicate_key_rows']} duplicate key rows; "
      f"after cleaning remaining nulls = {int(clean.isna().sum().sum())}.")
print(f"3. Peak system delay month: {peak_month['period'].strftime('%Y-%m')} "
      f"at {peak_month['pct_delayed']:.1f}% delayed.")
print("4. Delay-minute cause shares:")
for col, share in cause_share.sort_values(ascending=False).items():
    print(f"   - {col}: {share:.1f}%")
print("5. Highest airport delay rates (arrival-weighted):")
for _, row in top_airports.head(3).iterrows():
    print(f"   - {row['airport']} ({row['airport_name']}): {row['pct_delayed']:.1f}%")
print(
    f"6. OpenFlights airport join: {airport_match['n_airports_matched']}/"
    f"{airport_match['n_airports_in_delay']} airports matched "
    f"({airport_match['match_rate_airports']}%); "
    f"{airport_match['n_rows_matched']:,}/{airport_match['n_rows_before']:,} rows "
    f"({airport_match['match_rate_rows']}%). Source: {OPENFLIGHTS_SOURCE_URL}"
)
lat_rho = geo_corr.loc[(geo_corr['geo_feature'] == 'lat') & (geo_corr['outcome'] == 'pct_delayed'), 'spearman_rho'].iloc[0]
lon_rho = geo_corr.loc[(geo_corr['geo_feature'] == 'lon') & (geo_corr['outcome'] == 'pct_delayed'), 'spearman_rho'].iloc[0]
alt_rho = geo_corr.loc[(geo_corr['geo_feature'] == 'altitude_ft') & (geo_corr['outcome'] == 'pct_delayed'), 'spearman_rho'].iloc[0]
print(
    f"7. Location vs delay (airport-level Spearman): "
    f"lat-pct_delayed rho={lat_rho:.2f}, lon-pct_delayed rho={lon_rho:.2f}, "
    f"altitude-pct_delayed rho={alt_rho:.2f}."
)
print("8. Delay-rate distribution is right-skewed with high-volume hubs pulling long tails — "
      "IQR outliers are expected; treat as flags, not automatic deletes.")
```

### Reproducibility checklist

## 8. Reproducibility checklist

- [ ] Raw CSV + column definitions in `data/raw/`
- [ ] OpenFlights `airports.dat` in `data/raw/` (from https://github.com/jpatokal/openflights/blob/master/data/airports.dat)
- [ ] Project `.venv` created and `pip install -r requirements.txt`
- [ ] Kernel restarted & notebook run top-to-bottom
- [ ] Figures saved under `reports/figures/`
- [ ] Cleaned + airport-enriched data saved under `data/processed/`
- [ ] Written report describes cleaning, **dataset integration (match rates)**, summary stats, and visualization insights (no code dumps)
- [ ] Data provenance noted in `docs/data_sources.md`

---

## From `02_association_rules.ipynb`

### Discussion prompts / draft ARM insights

## 6. Discussion prompts (for the P1 writeup)

Use outputs above; rewrite in your own words:

1. **Interesting patterns** — Which antecedents most often lift `high_delay`, `weather_dominant`, or `late_aircraft_dominant`? Do region / season / altitude show up?
2. **min_support tradeoff** — What happens to rule count as support rises from 0.02 → 0.15? Which support would you defend for the report?
3. **Apriori vs FP-Growth** — Same itemsets here; note runtime/scalability difference for larger baskets.
4. **Strategic insight** — e.g. if `is_summer` + certain hubs associate with `high_delay`, that supports seasonal ops staffing; if `weather_dominant` ties to `northern` / winter, that foreshadows a weather-data join.
5. **Limits** — Monthly aggregates blur day-level storms; one-hots for only top carriers/airports miss smaller players; thresholds (Q75, 35% share) are choices — sensitivity matters.

Last captured notebook output:

```text
=== Draft ARM insights (edit for your report) ===

1. Built 44 binary items on 8,963 monthly transactions.
2. At min_support=0.05, apriori and fpgrowth found 667 itemsets (identical sets).
3. association_rules produced 2,985 rules (confidence≥0.3); 1,843 touch a delay/cause item.
4. Highest-lift delay-related rules:
   - {late_aircraft_dominant, many_runways, northern, tz_Central} => {region_Midwest} (support=0.053, conf=1.000, lift=7.20)
   - {late_aircraft_dominant, northern, tz_Central} => {many_runways, region_Midwest} (support=0.053, conf=1.000, lift=7.20)
   - {hub_Large, late_aircraft_dominant, northern, tz_Central} => {region_Midwest} (support=0.053, conf=1.000, lift=7.20)
   - {late_aircraft_dominant, northern, tz_Central} => {hub_Large, region_Midwest} (support=0.053, conf=1.000, lift=7.20)
   - {late_aircraft_dominant, northern, tz_Central} => {region_Midwest} (support=0.053, conf=1.000, lift=7.20)
   - {hub_Large, late_aircraft_dominant, many_runways, northern, tz_Central} => {region_Midwest} (support=0.053, conf=1.000, lift=7.20)
   - {hub_Large, late_aircraft_dominant, northern, tz_Central} => {many_runways, region_Midwest} (support=0.053, conf=1.000, lift=7.20)
   - {late_aircraft_dominant, many_runways, northern, tz_Central} => {hub_Large, region_Midwest} (support=0.053, conf=1.000, lift=7.20)
5. min_support sweep:
   - support=0.02: 2,719 itemsets, 11,172 delay-related rules
   - support=0.05: 667 itemsets, 1,843 delay-related rules
   - support=0.08: 313 itemsets, 594 delay-related rules
   - support=0.10: 203 itemsets, 336 delay-related rules
   - support=0.15: 101 itemsets, 150 delay-related rules
```

Snippet used to print the compact snapshot:

```python
# Compact “report-ready” snapshot
top_lift = rules_delay.head(8).copy()
top_lift["antecedents"] = top_lift["antecedents"].apply(lambda s: ", ".join(sorted(s)))
top_lift["consequents"] = top_lift["consequents"].apply(lambda s: ", ".join(sorted(s)))

print("=== Draft ARM insights (edit for your report) ===\n")
print(f"1. Built {meta['n_items']} binary items on {meta['n_rows']:,} monthly transactions.")
print(f"2. At min_support={MIN_SUPPORT}, apriori and fpgrowth found {len(freq_fp):,} itemsets (identical sets).")
print(f"3. association_rules produced {len(rules):,} rules (confidence≥{MIN_CONFIDENCE}); "
      f"{len(rules_delay):,} touch a delay/cause item.")
print("4. Highest-lift delay-related rules:")
for _, row in top_lift.iterrows():
    print(
        f"   - {{{row['antecedents']}}} => {{{row['consequents']}}} "
        f"(support={row['support']:.3f}, conf={row['confidence']:.3f}, lift={row['lift']:.2f})"
    )
print("5. min_support sweep:")
for _, row in sweep.iterrows():
    print(
        f"   - support={row['min_support']:.2f}: "
        f"{int(row['n_itemsets']):,} itemsets, "
        f"{int(row['n_delay_related_rules']):,} delay-related rules"
    )
```

### Reproducibility

## 7. Reproducibility

- [ ] `pip install -r requirements.txt` (includes `mlxtend`)
- [ ] Enriched panel present: `data/processed/airline_delay_cause_with_airports.csv`
- [ ] Run this notebook top-to-bottom
- [ ] Figures: `reports/figures/09_arm_minsupport_sweep.png`
- [ ] Exports: `association_binary_matrix.csv`, `association_rules_min_support_0_05.csv`
- [ ] Writeup covers binary encoding, both miners, rules, and min_support sensitivity

---

## Clustering (`03_clustering.ipynb`)

Numbers below come from running `src/clustering.py` on `data/processed/airline_delay_cause_with_airports.csv`. Re-run `notebooks/03_clustering.ipynb` to reproduce the tables and figures. FAA staffing is not a clustering feature.

## What we clustered

Each row is still one carrier–airport–month. We clustered the **shape of the month**, not raw flight counts, so a big hub does not land in its own cluster just for being big.

Features, after `StandardScaler`:

- `pct_delayed`, `pct_cancelled`
- share of delay minutes: carrier, weather, NAS, late aircraft

Months with `arr_flights` below the 10th percentile are left out. That cutoff is **32 arrivals**. A month with only a handful of flights can swing from 0% to 100% delayed off one flight, so it is a weak cluster member. That drops 894 rows. **8,069** months remain (from 8,963).

Security’s share of delay minutes has standard deviation **0.011**, so it barely moves. We left it out of the feature list. Months with no delay minutes get cause shares of 0.

Airport, season, and slot status are **not** inputs. We look at them after the clusters are formed.

---

## Why these two algorithms

We wanted a small set of delay regimes, then a second method on the **same scaled matrix** so differences come from the algorithm.

- **K-Means** puts every month into one group and is the usual first cut for numeric profiles.
- **Ward hierarchical** also uses Euclidean distance after scaling, but it builds groups by merging. Same k lets us compare partitions the way notebook 02 compared apriori and FP-Growth at the same support.

We did not cluster the 30 airports by themselves. That sample is too small for a stable k, and the EDA already ranks airports by delay rate.

---

## Parameter choices

`k` runs from 2 to 8. We take the k with the highest K-Means silhouette (`n_init=10`, `random_state=42`). Ward is cut at that same k.

| k | K-Means inertia | K-Means silhouette | Ward silhouette |
|---|-----------------|--------------------|-----------------|
| 2 | 39,676 | 0.225 | **0.236** |
| 3 | 32,574 | 0.236 | 0.197 |
| 4 | 28,108 | 0.248 | 0.216 |
| **5** | 24,494 | **0.255** | 0.213 |
| 6 | 22,040 | 0.217 | 0.177 |
| 7 | 20,669 | 0.196 | 0.181 |
| 8 | 19,577 | 0.186 | 0.133 |

**Chosen k = 5.** Inertia falls smoothly, so there is no sharp elbow. Silhouette peaks at 5 and is only a little higher than at 4 (0.248). Separation is modest either way: 0.255 is not a tight grouping. Months overlap.

Ward’s own silhouette is best at **k = 2** (0.236), not at 5 (0.213). If each method picked its own k, Ward would stop at a coarser split. We still cut Ward at 5 so the comparison is about membership, not about a different number of groups.

Figure: `reports/figures/13_cluster_silhouette_vs_k.png`.

---

## PCA

PCA is fit on the same scaled features. Share of variance:

| PC1 | PC2 | PC3 | PC4 | PC5 | PC6 |
|-----|-----|-----|-----|-----|-----|
| 28.9% | 24.2% | 19.4% | 15.7% | 11.8% | ~0% |

The first two components explain **53%**. Our rule was to cluster in PC1–PC2 only if they explained at least 70%. They do not, so **clustering stays in the 6-feature scaled space**. The last component is almost zero because the cause shares add up to about 1. One share is basically determined by the others.

The scatters (`14_kmeans_pca_scatter.png`, `15_ward_pca_scatter.png`) are a flattened view. The middle of the cloud mixes colors. That matches the silhouette: groups are real enough to profile, but they are not separated blobs in two dimensions.

---

## What the clusters mean

Means below are inside the cluster. “Slot %” is the share of rows at JFK, LGA, EWR, or DCA. In the full clustered set that share is **12.7%**. IQR outlier % is the share of rows flagged on `pct_delayed` (overall **1.4%**). We still do not delete those rows.

### K-Means

| Cluster | Rows | Delayed 15+ | Cancelled | Main cause share | Slot % | IQR outlier % | Often |
|---------|------|-------------|-----------|------------------|--------|---------------|-------|
| 0 | 3,616 (45%) | 22.7% | 1.1% | late aircraft 0.49 | 6.5 | 0.5 | DTW, CLT, IAD |
| 1 | 1,737 (22%) | 25.2% | 1.3% | NAS 0.46 | 24.1 | 3.0 | EWR, SFO, DCA |
| 2 | 1,454 (18%) | 18.1% | 0.9% | carrier 0.56 | 8.5 | 0.2 | PHX, LAX, BNA |
| 3 | 846 (10%) | 28.9% | 7.2% | late aircraft 0.40, NAS 0.25 | 26.1 | 4.4 | LGA, DCA, EWR; winter 41% |
| 4 | 416 (5%) | 20.9% | 2.0% | weather 0.26, carrier 0.39 | 7.7 | 0.2 | DFW, ATL, MSP |

Plain reading:

- **Cluster 0** is the common month. Late aircraft is about half of delay minutes. Delay rate is near the middle of the set. This is the cascade pattern already dominant in the EDA minute shares (late aircraft was 38.7% of all delay minutes).
- **Cluster 1** is NAS-heavy. Delay rate is a bit higher. Slot airports and SFO show up more than in the common month (24% vs 12.7% base).
- **Cluster 2** is carrier-heavy and has the **lowest** delay rate. A carrier-cause month is not the same thing as a bad month.
- **Cluster 3** is the disruption month: highest delay rate and cancellations around 7%, versus about 1% elsewhere. Winter is the most common season (41%). Slot airports are 26% of the rows. IQR delay-rate outliers are more common here (4.4%) than in the common month (0.5%).
- **Cluster 4** is small. Weather’s share of minutes jumps to 0.26, against about 0.03–0.05 in the other groups. The delay rate is not the worst. Weather-heavy does not mean the highest percent delayed.

### Ward at the same k

| Cluster | Rows | Delayed 15+ | Cancelled | Main cause share | Slot % | Lines up with K-Means |
|---------|------|-------------|-----------|------------------|--------|------------------------|
| 0 | 4,345 (54%) | 23.6% | 1.4% | late aircraft 0.47 | 8.5 | mostly K-Means 0 |
| 1 | 540 (7%) | 19.6% | 1.6% | carrier 0.48, weather 0.22 | 8.5 | mostly K-Means 4 |
| 2 | 1,573 (19%) | 23.7% | 1.5% | NAS 0.47 | 24.8 | mostly K-Means 1 |
| 3 | 393 (5%) | 27.6% | 9.1% | late aircraft 0.38 | 32.1 | the core of K-Means 3; winter 46% |
| 4 | 1,218 (15%) | 19.8% | 1.4% | carrier 0.56 | 8.0 | mostly K-Means 2 |

Figure: `reports/figures/16_cluster_profile_heatmap.png`.

---

## How the two methods compare

Adjusted Rand index is **0.60**. That is agreement well above chance, not a copy of the same labels.

Crosstab (rows = K-Means, columns = Ward):

|  | Ward 0 | Ward 1 | Ward 2 | Ward 3 | Ward 4 |
|--|--------|--------|--------|--------|--------|
| K-Means 0 | 3,475 | 2 | 61 | 0 | 78 |
| K-Means 1 | 319 | 7 | 1,360 | 7 | 44 |
| K-Means 2 | 201 | 177 | 67 | 0 | 1,009 |
| K-Means 3 | 284 | 8 | 84 | 384 | 86 |
| K-Means 4 | 66 | 346 | 1 | 2 | 1 |

Same story, different edges:

- Both find a large late-aircraft group, a NAS group, a carrier group, a high-cancel group, and a smaller weather-leaning group.
- Ward’s cancel group is tighter (393 rows, 9.1% cancelled) than K-Means (846 rows, 7.2%). K-Means pulls some milder months into that group; 284 of its cancel-cluster rows sit in Ward’s big late-aircraft group.
- Ward’s weather-leaning group also carries a high carrier share (0.48). K-Means keeps weather (0.26) a bit cleaner.
- The main discrepancy on **k** is above: Ward’s silhouette prefers 2 groups. The five-group cut is a K-Means choice that Ward only partly supports.

---

## What this is useful for

- Most carrier-months look like **late-aircraft** delay. That is a turnaround and schedule problem, not a one-day storm story.
- **NAS-heavy** months are the ones where airport and airspace ops matter more. They show up more often at EWR, SFO, and the New York / DC slot airports, but those airports are still a minority of the cluster.
- **Cancellation spikes** are their own pattern. They are more winter and more often at LGA, DCA, and EWR. Planning for a bad delay rate is not the same as planning for a cancellation day.
- **Carrier-dominant** months have lower delay rates. Chasing carrier-cause share by itself will not point at the worst months.
- Weather’s share can be high without the month having the worst delay rate. A weather join would still help, but this extract already separates “weather is a large slice of minutes” from “the month was heavily delayed or cancelled.”

---

## Outliers

IQR flags stay flags. They are not removed before clustering.

On `pct_delayed`, we recompute the same 1.5-IQR rule on the months that entered clustering. Flagged rows are **1.4%** of those months. They pile up in the high-cancel group (K-Means 4.4%, Ward 4.1%) and the NAS group (K-Means 3.0%, Ward 2.3%). The carrier and weather groups are almost free of them (about 0.2%). The heavy tail from notebook 01 shows up here as the disruption months, which is why we did not drop those rows first. Notebook 05 tests that choice. Dropping the 111 delay-rate IQR flags leaves the cancellation cluster intact. Dropping every outlier flag softens it. The comparison is in the outlier-impact section below.

Notebook 03 does not add a second outlier algorithm, and it does not drop these flags before clustering. The comparison with k-NN distance and an isolation forest is in `notebooks/04_outlier_detection.ipynb` and in the outlier section below.

---

## Limits

- A month is a coarse bucket. One storm day and a calm rest of the month land in the same row.
- Months under 32 arrivals are out. Small-carrier months are under-represented.
- Silhouette around 0.25 means these are tendencies, not crisp types. Do not treat a cluster id as a hard label in the report without the profile table.
- Cause shares compete. If late aircraft goes up, something else goes down.
- k = 5 is the K-Means peak, and k = 4 is close. Say that when defending the choice.
- FAA staffing is still a separate file. It was not used here.

### Reproducibility

- [ ] `pip install -r requirements.txt` (includes `scikit-learn`)
- [ ] Enriched panel present: `data/processed/airline_delay_cause_with_airports.csv`
- [ ] Run `notebooks/03_clustering.ipynb` top-to-bottom
- [ ] Figures: `reports/figures/13_` through `16_`
- [ ] Exports: `cluster_assignments.csv`, `cluster_k_sweep.csv`, `cluster_profiles.csv`, `cluster_method_crosstab.csv`

---

## Outlier detection (`04_outlier_detection.ipynb`)

Numbers below come from `src/outliers.py` on the same enriched panel. Re-run `notebooks/04_outlier_detection.ipynb` to reproduce the tables and figures. FAA staffing is not a feature.

## What we call an outlier

An outlier is a carrier–airport–month whose delay profile is unusual relative to the other months in this extract. A merely bad month is not an outlier if many other months look like it. We flag rows. We do not delete them.

The scored population is the clustering population: `arr_flights` at or above the 10th percentile (**32** arrivals). That drops 894 rows. **8,069** months remain (from 8,963). Tiny months can swing from 0% to 100% delayed off one flight, and they would dominate a distance score.

Features match clustering. k-NN and the isolation forest see them after `StandardScaler`:

- `pct_delayed`, `pct_cancelled`
- share of delay minutes: carrier, weather, NAS, late aircraft

Security’s share stays out (standard deviation **0.011**). IQR fences are computed on the raw rates, not on the scaled columns. Airport, season, and slot status are not inputs. We read them after the flags are set.

Three rules:

1. **IQR rates (statistical threshold).** A month is flagged when `pct_delayed` or `pct_cancelled` falls outside the Tukey fence, Q1 − 1.5×IQR to Q3 + 1.5×IQR, on this population.
2. **k-NN distance.** Score = mean Euclidean distance to the **15** nearest other months in the scaled space. A month is flagged when that score is above the upper Tukey fence of the scores. Only the high side counts. A small distance means the month has neighbors.
3. **Isolation forest.** 200 trees, `contamination=0.05`, `random_state=42`. A month is flagged when `decision_function` < 0. The contamination setting is what holds the flag rate near 5%.

**Consensus** means at least two of the three rules flag the month. That is the set to quote if the report wants one list. The single-method flags are still worth describing, because they are different kinds of unusual.

| Method | Rule on this run | Flagged |
|---|---|---|
| IQR rates | `pct_delayed` outside [−0.52, **45.31**] or `pct_cancelled` outside [−3.09, **5.64**] | **713** (8.84%) |
| k-NN, k=15 | mean distance > **1.189** | **436** (5.40%) |
| Isolation forest | `decision_function` < 0 at contamination 0.05 | **404** (5.01%) |
| Consensus (2+) | at least two of the three | **365** (4.52%) |

Both lower fences sit below 0, and neither rate can be negative, so the IQR rule is an **upper-tail** rule here. Of the 713 IQR flags, **111** fail the delay fence, **621** fail the cancel fence, and **19** fail both. The delay-only piece is the same 1.4% the clustering notes already use (`111 / 8,069`). Most of the IQR union is the cancellation tail, which is long because a typical month is near 1% cancelled (inlier mean **1.23%**) while the upper fence is only **5.64%**.

`contamination='auto'` would have flagged **1,271** months (**15.75%**). That is a wide band of somewhat unusual profiles, not a tail. We set 0.05 so the forest marks a share close to the k-NN tail (~5.4%) and the comparison is about *which* months, not about a much larger net.

k changes the neighborhood, not the story. The same upper-fence rule at other k:

| k | Upper fence | Flagged | Jaccard with k=15 |
|---|-------------|---------|-------------------|
| 5 | 0.961 | 433 (5.37%) | 0.803 |
| **15** | **1.189** | **436 (5.40%)** | 1.000 |
| 30 | 1.379 | 435 (5.39%) | 0.910 |

---

## How the three flags overlap

| Pair | Both | Either | Jaccard |
|---|------|--------|---------|
| IQR and k-NN | 236 | 913 | 0.258 |
| IQR and isolation forest | 166 | 951 | 0.175 |
| k-NN and isolation forest | 269 | 571 | **0.471** |

All three agree on **153** months. Any method flags **1,035** months. The other **7,034** (87.2%) are inliers on every rule.

| Pattern | Rows | What it means |
|---|---|---|
| inlier | 7,034 | none of the three |
| rate only | 464 | IQR, and neither distance method |
| shape only | 322 | k-NN or the forest, and not IQR |
| rate and shape | 249 | IQR and at least one distance method |

k-NN and the forest agree with each other much more than either agrees with IQR. That is the result to explain, not a failure of one method. IQR asks whether a **rate** is in the tail. The other two ask whether the **profile** is isolated. A system-wide cancellation month fails the first test and often passes the second, because many rows share that shape, so none of them is a lonely neighbor.

Figures: `reports/figures/17_outlier_pca_scatter.png` (patterns on PC1–PC2, **53%** of scaled variance — a view, not the space the distance methods used), `18_outlier_score_thresholds.png`, `19_outlier_profile_heatmap.png`, `20_outlier_counts_by_month.png`.

---

## What the groups look like

Means are inside the group. “Slot %” is the share of rows at JFK, LGA, EWR, or DCA. Inliers are **11.1%** slot. Median `arr_flights` for inliers is **570**.

| Group | Rows | Median flights | Delayed 15+ | Cancelled | Carrier | Weather | NAS | Late aircraft | Slot % | Winter % |
|---|---|---|---|---|---|---|---|---|---|---|
| inlier | 7,034 | 570 | 22.4% | 1.2% | 0.33 | 0.04 | 0.24 | 0.38 | 11.1 | 22.0 |
| rate only | 464 | 456 | 28.2% | 7.0% | 0.31 | 0.05 | 0.25 | 0.39 | 25.9 | 46.8 |
| shape only | 322 | 101 | 20.9% | 1.5% | 0.40 | 0.19 | 0.25 | 0.16 | 13.7 | 24.5 |
| rate and shape | 249 | 175 | 32.1% | 8.5% | 0.28 | 0.09 | 0.33 | 0.29 | 32.9 | 32.9 |
| consensus (2+) | 365 | 132 | 28.2% | 6.4% | 0.28 | 0.15 | 0.31 | 0.26 | 26.0 | 30.7 |

### Rate only — extreme cancellations, ordinary cause mix

The cause shares sit on top of the inlier mix. Late aircraft is still about 0.39. What moves is the cancellation rate (7.0% vs 1.2%) and, less so, the delay rate (28.2% vs 22.4%). Winter is **46.8%** of the group, against 22% of inliers. Summer is also heavy (36.6% vs 27.7%). Slot airports are 25.9% of the rows.

These months are extreme and **not isolated**. Other months in the same bad stretch look like them, so k-NN and the forest leave many of them alone.

The calendar makes that concrete (`20_outlier_counts_by_month.png`):

- **January 2026:** 132 of 314 scored months fail the IQR rule, across **18 carriers and 27 airports**. k-NN flags 50 of that month, the forest 32, consensus 47. Median cancellation among the January IQR rows is about **8.4%**, with a delay rate near 23%. That is a system month, not one carrier’s file.
- **February 2026:** 80 IQR flags.
- **July 2024:** 70 of 335. **July 2025:** 64 of 334.

The 111 delay-fence months (upper fence 45.31%) are the sharper delay tail inside this rule: mean delay about **51%**, NAS share about **0.39**, carrier share about **0.25**. They concentrate at SFO, EWR, and ORD, and in summer more than winter. Southwest at SFO in June 2026 is the top of that tail: **74.9%** of 954 arrivals delayed, NAS share 0.49, cancellations under 1%. IQR and k-NN flag it. The forest does not (`decision_function` about +0.02). A high NAS month at SFO is less isolated than the rows the forest spends its 5% on.

### Shape only — unusual cause mix, ordinary rates

Mean delay **20.9%** and cancellations **1.5%** are close to the inliers. Weather’s share of delay minutes is **0.19** vs **0.04**. Late aircraft falls to **0.16** vs **0.38**. Median size is **101** arrivals, against 570 for inliers. Slot share is about the same as the inliers (13.7% vs 11.1%). Season mix is flat.

The farthest k-NN point is Allegiant (G4) at BOS in June 2024: **69** arrivals, **4** delays, delay rate **5.8%**, and **317 of 350** delay minutes coded weather (share **0.91**). June 2026 at the same carrier and airport repeats it (67 arrivals, weather share **0.85**). Both are k-NN and forest flags, not IQR flags. Allegiant at EWR in September 2025 is the other kind of isolated point: **37** arrivals and **zero** delay minutes, so every cause share is 0 (k-NN score **3.71**).

On a thin schedule, a few weather-delayed flights become almost the whole cause mix. The month is real. The share is also a small denominator. Twelve months in the scored set have a weather share above 0.50, and the k-NN rule flags all twelve.

### Rate and shape — the consensus core

These 249 months are high on both tests. Mean delay **32.1%**, cancellations **8.5%**, NAS share **0.33**, weather share **0.09**. Slot airports are **32.9%** of the rows. Median size is 175 arrivals, still well under the inlier median.

Examples from the extreme-score table:

- Endeavor (9E) at EWR, May 2025: **67.8%** delayed, **14.9%** cancelled, NAS share **0.69**. All three methods.
- Envoy (MQ) at EWR, May 2025: **21.9%** cancelled, NAS share **0.79**, carrier share **0.02**. All three methods. Spirit (NK) and Republic (YX) at EWR the same month are also at the bottom of the forest score, with NAS shares 0.89 and 0.83.
- SkyWest (OO) at LGA, March 2026: **22.7%** cancelled on 44 arrivals. All three methods.
- Southwest at SFO, May 2026: **67.0%** delayed on 858 arrivals, NAS share **0.61**. All three methods.

May 2025 at EWR shows up as several carriers at once, which looks like an airport month rather than a single reporting glitch. The consensus list as a whole (365 months) has median **132** flights, delay **28.2%**, cancellations **6.4%**, weather share **0.15**, and slot share **26%**.

Carriers split with the pattern. The IQR union is heavy on regional and lower-cost flying at the slot airports (OH, NK, B6, YX, 9E in the raw counts). Shape flags pick up thinner schedules (OO, G4) where one cause can take the minutes. That is schedule size and cause mix, not a label for one airline.

---

## What might cause these rows

**Data entry.** On the 8,069 scored months the logical checks find no negative counts, no delay or cancellation count above arrivals, and no bad month numbers. Cause-count mismatches: **6** rows. Cause-minute mismatches beyond a 1-minute tolerance: **29** rows (0.36%). Only **one** of those 29 is also an outlier: Southwest at DTW in June 2026, **8,588** arrival-delay minutes against **8,083** minutes summed across causes, delay rate **45.5%** (just over the 45.31 fence). IQR flags it. k-NN and the forest do not. The gap is a reporting inconsistency. It does not explain the other thousand flags. We still do not drop the row.

**Rare but valid operations.** January 2026 and the two Julys are many carriers at many airports in the same month. In a monthly extract, that is what a system disruption looks like: winter cancellations, summer delay rates, and a larger share of slot-airport rows. The clustering write-up already put IQR delay-rate flags into the high-cancel and NAS clusters. This screen shows the same months without using the cluster labels as inputs.

The shape-only rows are the other valid tail. A month can be ordinary on both rates and still be almost entirely weather minutes, because only a few flights were delayed. That matches the clustering note that a high weather share is not the same thing as a high delay rate. It is also why a distance method is worth running next to a rate fence.

**Fraudulent activity.** This file is BTS on-time reporting, not payments or identities. There is no transaction here to call fraudulent in the usual sense. Airlines do have a reason to code a delay as NAS or weather rather than carrier, because carrier-cause delay is the piece the DOT rankings emphasize. The delay-fence tail does show a higher NAS share (about 0.39 vs about 0.25) and a lower carrier share. That is also what a bad airspace month looks like at SFO, EWR, and ORD, and the same months hit many carriers at once. A monthly total cannot separate a coding incentive from a real NAS day. We would not call these rows fraud. A check aimed at cause-code shifting would need day-level codes, a carrier’s own baseline, and a rule for “the code moved and the operation did not.” This screen does not do that.

---

## Limits

- A month mixes a storm day with the calm days around it. Both the rate fence and the cause shares are diluted the same way.
- Months under 32 arrivals are out. The shape-only group is still the thinner part of what remains (median about 100 arrivals). Small denominators inflate cause shares.
- Cause shares compete. A weather share of 0.91 forces the other shares down.
- The cancellation IQR flags 621 months (7.7%). That is a long operational tail, not a handful of impossible values. Say so if the report quotes the 8.8% union.
- The forest’s 5% is a chosen budget. `contamination='auto'` is much wider. k=15 is stable against k=5 and k=30, but it is still a choice.
- PC1–PC2 explain 53%. The scatter will show overlap even when the six-feature score says isolated.
- FAA staffing is still a separate file. It was not used here.

### Reproducibility

- [ ] `pip install -r requirements.txt` (includes `scikit-learn`)
- [ ] Enriched panel present: `data/processed/airline_delay_cause_with_airports.csv`
- [ ] Run `notebooks/04_outlier_detection.ipynb` top-to-bottom
- [ ] Figures: `reports/figures/17_` through `20_`
- [ ] Exports: `outlier_scores.csv`, `outlier_method_summary.csv`, `outlier_agreement.csv`, `outlier_profiles.csv`, `outlier_knn_sweep.csv`, `outlier_monthly_counts.csv`, `outlier_examples.csv`
- [ ] Write-up keeps the three rules separate from the consensus list, and treats flags as flags

---

## Outliers and clustering (`05_outlier_clustering_impact.ipynb`)

Numbers below come from `src/cluster_outlier_impact.py`. Re-run `notebooks/05_outlier_clustering_impact.ipynb` to reproduce the tables and figures. The published clustering is the **retain** row. Removals happen after the 32-arrival cutoff. That cutoff is not recomputed. Each refit standardizes only the rows it keeps and chooses k from the K-Means silhouette, same rule as notebook 03.

Cluster ids are not comparable across fits. A refit group is named for the retained group whose mean profile is closest, after each mean is scaled by the spread of the five retained profiles. The names are late aircraft, NAS, carrier, cancellation, and weather.

## Where the flags sit in the retained fit

Consensus outliers are not spread evenly. Of the **365** consensus months, the retained K-Means groups hold:

| Retained K-Means role | Consensus months | Share of that cluster |
|---|---|---|
| late aircraft | 13 | 0.4% |
| NAS | 63 | 3.6% |
| carrier | 21 | 1.4% |
| cancellation | 155 | 18.3% |
| weather | 113 | 27.2% |

The cancellation months that are consensus outliers average **10.7%** cancelled. The weather months that are consensus outliers average a weather share of **0.36**. Those two tails are what a removal can change. The late-aircraft, NAS, and carrier groups are almost all inliers.

The 111 delay-rate IQR flags are a different set: 52 in NAS, 37 in cancellation, 18 in late aircraft, 3 in carrier, 1 in weather.

## What stays the same

Every removal still chooses **k = 5**. The silhouette peak does not move. PC1–PC2 stay near 53% of variance, so every fit stays in the six-feature space.

The five cause regimes are still there after the consensus removal and after the delay-rate removal: a large late-aircraft group, a NAS group, a carrier group, a higher-cancellation group, and a higher-weather group. Late aircraft stays near a 0.49 share. NAS stays near 0.46. Carrier stays near 0.56.

| Removal | Rows dropped | K-Means silhouette | K-Means vs Ward ARI | K-Means vs retained labels | Ward vs retained labels | Kept months in the same K-Means role |
|---|---|---|---|---|---|---|
| retain | 0 | 0.255 | 0.604 | 1.00 | 1.00 | 100% |
| drop consensus | 365 (4.5%) | 0.245 | 0.561 | 0.81 | 0.54 | 91% |
| drop delay IQR | 111 (1.4%) | 0.252 | 0.415 | 0.96 | 0.44 | 99% |
| drop any flag | 1,035 (12.8%) | 0.230 | 0.419 | 0.62 | 0.25 | 79% |

Figure: `reports/figures/21_outlier_removal_silhouette.png`.

## What changes

**Dropping the consensus outliers softens the two groups those flags live in.** It does not invent a new pattern or delete one.

K-Means cancellation mean falls from **7.16%** to **5.27%**. The group grows from 846 months to 1,088, because milder months join once the extreme tail is gone. Its most common season flips from winter (41%) to summer (45%). Ward’s cancellation group also falls, from **9.11%** to **5.79%**, and it stays a winter group (41%). Weather’s share falls from **0.26** to **0.19** (K-Means) and from **0.22** to **0.16** (Ward). The other three K-Means profiles barely move, and 91% of the kept months stay in the same K-Means role.

**Dropping only the 111 delay-rate IQR flags does not change the K-Means patterns.** Agreement with the retained labels is **0.96**. The cancellation mean is **7.10%** instead of 7.16%, still winter (42%), and the weather share is still **0.26**. The earlier worry that those flags were propping up the cancellation cluster is not what this refit shows. Ward is less steady: its silhouette falls from 0.213 to 0.165 and its agreement with the retained Ward labels is 0.44, but Ward still has a winter cancellation group at **7.46%** and a weather share of **0.28**.

**Dropping every flagged month does change the cancellation pattern.** That removes 1,035 months (12.8%). K-Means cancellation falls to **3.19%** and becomes a summer group (46%) with a late-aircraft share of 0.44. It is a higher-delay version of the common month, not a 7% winter cancellation regime. Ward’s highest cancellation mean is **2.58%**, also summer (49%). Weather share falls to **0.16** (K-Means) and **0.13** (Ward). The carrier, NAS, and late-aircraft groups are still recognizable. Membership moves: 79% of kept months keep their K-Means role, and only 58% keep their Ward role. The late-aircraft role is the one that leaks (71% stay).

Figure: `reports/figures/22_outlier_removal_profiles.png`.

## What to keep in the fit

Retain the outliers in the published clustering.

They are the sharp end of two real regimes, not a handful of bad rows that create a fake cluster. The consensus set is 4.5% of months and sits inside the cancellation and weather groups. Removing it leaves the same five stories at a duller volume, and it is enough to flip the K-Means cancellation season off winter. Removing every flag, including ordinary-rate months with an unusual cause mix, takes the winter cancellation pattern out of both algorithms.

The delay-rate fence alone is too small to be the reason those patterns exist. Keeping those 111 rows changes K-Means membership by about 1%.

---

### Reproducibility

- [ ] `pip install -r requirements.txt` (includes `scikit-learn` and `scipy`)
- [ ] Enriched panel present: `data/processed/airline_delay_cause_with_airports.csv`
- [ ] Run `notebooks/05_outlier_clustering_impact.ipynb` top-to-bottom
- [ ] Figures: `reports/figures/21_outlier_removal_silhouette.png`, `22_outlier_removal_profiles.png`
- [ ] Exports: `cluster_outlier_scenario_summary.csv`, `cluster_outlier_profiles.csv`, `cluster_outlier_stability.csv`, `cluster_outlier_k_sweep.csv`, `cluster_outlier_pattern_counts.csv`
- [ ] Write-up says the five cause regimes survive a consensus removal, and the winter cancellation regime does not survive dropping every flag



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

On `pct_delayed`, we recompute the same 1.5-IQR rule on the months that entered clustering. Flagged rows are **1.4%** of those months. They pile up in the high-cancel group (K-Means 4.4%, Ward 4.1%) and the NAS group (K-Means 3.0%, Ward 2.3%). The carrier and weather groups are almost free of them (about 0.2%). The heavy tail from notebook 01 shows up here as the disruption months, which is why we did not drop those rows first. Dropping them would have shrunk the cancel cluster on purpose.

We did not add a second outlier algorithm. The IQR rule is already the project’s outlier method. Clustering shows where those flags land.

---

## Limits

- A month is a coarse bucket. One storm day and a calm rest of the month land in the same row.
- Months under 32 arrivals are out. Small-carrier months are under-represented.
- Silhouette around 0.25 means these are tendencies, not crisp types. Do not treat a cluster id as a hard label in the report without the profile table.
- Cause shares compete. If late aircraft goes up, something else goes down.
- k = 5 is the K-Means peak, and k = 4 is close. Say that when defending the choice.
- FAA staffing is still a separate file. It was not used here.

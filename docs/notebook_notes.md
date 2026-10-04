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

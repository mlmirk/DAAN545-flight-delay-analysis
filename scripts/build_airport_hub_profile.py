"""Build data/raw/airport_hub_profile.csv from FAA + OurAirports (scratch downloads)."""
from __future__ import annotations

import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

CODES = [
    "ATL",
    "AUS",
    "BNA",
    "BOS",
    "BWI",
    "CLT",
    "DCA",
    "DEN",
    "DFW",
    "DTW",
    "EWR",
    "FLL",
    "IAD",
    "IAH",
    "JFK",
    "LAS",
    "LAX",
    "LGA",
    "MCO",
    "MDW",
    "MIA",
    "MSP",
    "ORD",
    "PHL",
    "PHX",
    "SAN",
    "SEA",
    "SFO",
    "SLC",
    "TPA",
]
SLOT_CONTROLLED = {"JFK", "LGA", "EWR", "DCA"}
HUB_LABEL = {"L": "Large", "M": "Medium", "S": "Small", "N": "Nonhub"}

FAA_XLSX = (
    "https://www.faa.gov/sites/faa.gov/files/2024-10/cy23-commercial-service-enplanements.xlsx"
)
OA_AIRPORTS = "https://davidmegginson.github.io/ourairports-data/airports.csv"
OA_RUNWAYS = "https://davidmegginson.github.io/ourairports-data/runways.csv"

scratch_faa = RAW / "_cy23_enplanements.xlsx"
scratch_air = RAW / "_airports_oa_tmp.csv"
scratch_rwy = RAW / "_runways_tmp.csv"

print("Downloading FAA CY23 enplanements…")
urllib.request.urlretrieve(FAA_XLSX, scratch_faa)
print("Downloading OurAirports airports + runways…")
urllib.request.urlretrieve(OA_AIRPORTS, scratch_air)
urllib.request.urlretrieve(OA_RUNWAYS, scratch_rwy)

faa = pd.read_excel(scratch_faa, header=0)
faa.columns = [str(c).strip() for c in faa.columns]
# Expected: Locid, Hub, CY 23 Enplanements (names may vary slightly)
loc_col = next(c for c in faa.columns if c.lower() in {"locid", "loc_id"})
hub_col = next(c for c in faa.columns if c.lower() == "hub")
enp_col = next(c for c in faa.columns if "23" in c and "enplane" in c.lower())

faa[loc_col] = faa[loc_col].astype(str).str.strip().str.upper()
hub = faa[faa[loc_col].isin(CODES)][[loc_col, hub_col, enp_col]].copy()
hub = hub.rename(
    columns={
        loc_col: "airport",
        hub_col: "hub_code",
        enp_col: "enplanements_cy23",
    }
)
hub["hub_code"] = hub["hub_code"].astype(str).str.strip().str.upper()
hub["hub_size"] = hub["hub_code"].map(HUB_LABEL).fillna(hub["hub_code"])
hub["enplanements_cy23"] = pd.to_numeric(hub["enplanements_cy23"], errors="coerce")

oa = pd.read_csv(scratch_air, low_memory=False)
oa = oa[oa["iata_code"].isin(CODES)][["ident", "iata_code"]].drop_duplicates("iata_code")
rwy = pd.read_csv(scratch_rwy, low_memory=False)
if "closed" in rwy.columns:
    rwy = rwy[rwy["closed"].fillna(0).astype(int) == 0]
counts = rwy.groupby("airport_ident").size().rename("runway_count").reset_index()
runways = oa.merge(counts, left_on="ident", right_on="airport_ident", how="left")
runways = runways.rename(columns={"iata_code": "airport"})[
    ["airport", "runway_count", "ident"]
]
runways["airport"] = runways["airport"].astype(str).str.upper()

profile = pd.DataFrame({"airport": CODES}).merge(hub, on="airport", how="left")
profile = profile.merge(runways, on="airport", how="left")
profile["slot_controlled"] = profile["airport"].isin(SLOT_CONTROLLED)
profile["faa_hub_year"] = 2023
profile["icao_ident"] = profile["ident"]
profile = profile.drop(columns=["ident"], errors="ignore")
profile = profile[
    [
        "airport",
        "hub_size",
        "hub_code",
        "enplanements_cy23",
        "slot_controlled",
        "runway_count",
        "icao_ident",
        "faa_hub_year",
    ]
].sort_values("airport")

out = RAW / "airport_hub_profile.csv"
profile.to_csv(out, index=False)
print(f"Wrote {out} ({len(profile)} airports)")
print(profile.to_string(index=False))
missing = profile[profile["hub_size"].isna() | profile["runway_count"].isna()]
if len(missing):
    print("WARNING missing fields:\n", missing)

# remove scratch (gitignore also covers _*)
for p in (scratch_faa, scratch_air, scratch_rwy):
    p.unlink(missing_ok=True)
print("Scratch downloads removed.")

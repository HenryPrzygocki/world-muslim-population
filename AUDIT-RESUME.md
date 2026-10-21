# Audit in progress: remove every value based on my own guesswork

**Rule (from Henry, 21 Oct 2026):** every number on the map must be either a published figure or plain arithmetic
on published figures (sums, count ÷ official population). No values I chose myself: no modelled regional
patterns, no default/fallback percentages, no rounded proxies, no hand adjustments, no allocations of a national
total by my judgment. Where no figure was collected, the area shows **no figure** (hatched); it is not filled with
a national or guessed value.

Status: **paused mid-way.** This work lives on branch `audit-no-guesswork`; `main` (the live site) is unchanged.

## Done so far (code edited, NOT yet rebuilt or tested)

`pipeline/scripts/mapkit.py`
- Latin American communities whose number was an allocation of Pew's national total (basis `estimate`) are now
  uncounted markers (`unsized`); counted (census) and uncounted places are never merged into one circle.
  Result: Foz do Iguaçu = 5,599 (IBGE 2010 census); Ciudad del Este, Asunción, Chuy, Buenos Aires… = no count.

`pipeline/scripts/build_units.py` (backup of the previous version: none in repo — see git history on `main`)
- `add()` keeps areas with no figure (pct NaN + `dflt`) so they render as "no figure" instead of the national fill.
- Share × population ("≈") counts disabled (the populations were not from a cited table).
- Territories: only sourced values kept (Somaliland = Pew Somalia; Liechtenstein & Gibraltar censuses; Indian
  Ocean Territories ABS). Cyprus, Northern Cyprus, Akrotiri, Dhekelia = Pew whole-island figure. All other small
  territories I had given guessed values → no value. French overseas departments use their own Pew figures
  (`GEOU`), Caribbean Netherlands → no value.
- UK: Scottish/NI councils without a census figure → no value (were 0.5% / 0.3% defaults); derived counts removed.
- Russia: rows with basis "estimate", "(estimate)" or "~" removed; unmatched regions → no value (was 0.9%).
- China: "approx." provinces removed; unmatched → no value (was 0.15%); Xinjiang prefecture composites removed.
- Thailand: the 31 provinces set to 0.1% → no value.
- Removed subnational layers entirely (country shows Pew national value): PAK (100 − Hindu − my 0.6%), KGZ
  (rounded "non-Slavic" proxy), MNG, PSX split (85/99), EGY, NGA, TZA, MOZ, GHA (whole table was my estimates),
  CIV, CMR, TCD, TGO, SLE, LBR, ERI, CAF, MDG, SEN, KOS, GRC, DEU, CHE, BEL, FRA (mainland).
- Burkina Faso: only the 2006-census provinces; 5 modelled regions → no value.
- Benin: only the 4 departments with 2013 census figures; others → no value.
- North Macedonia: removed my 21% for Skopje → no value.
- Montenegro: re-estimated post-2013 municipalities (Plav, Gusinje, Berane, Petnjica) → no value; Tuzi + Zeta merged
  into Podgorica with its 2011 value (they were part of Podgorica in 2011).
- Serbia: municipalities not collected → no value (was 0.5%).
- Georgia: Abkhazia (derived from a guessed share) → no value.
- Romania: Tulcea → no value; Constanța = 36,725 ÷ 656,000 (INS 2021 press release: 656.0 thousand residents).
- Spain: provinces = UCIDE count (31 Dec 2017) ÷ INE official population (1 Jan 2018), now stored in
  `pipeline/data/sub2/ESP_prov.csv` (`ine_pop_2018`). No more scaling to a 2024 total or rounded populations.

`pipeline/data/sub/MMR.csv`: Rakhine back to the published 2014 census value 35.1% (incl. the census's own estimate
for its non-enumerated population); my displacement adjustment and 600,000 count removed.

## Still to do (in this order)

1. **Finish the scan** — remaining suspects found but not yet fixed:
   - `ETH.csv`: 14 zones marked "remainder (approx.)" → remove (no value).
   - `GBR_SN.csv`: only Glasgow, Edinburgh, Aberdeen, Dundee are from Scotland's Census 2022; drop East
     Renfrewshire … West Lothian and Belfast (approximations).
   - `BIH.csv`: all canton values are whole numbers ("Bosniak/Muslim share") — verify against the 2013 census
     religion table or drop.
   - `RUS.csv` integer rows with plain "2021 census ethnicity" (Chelyabinsk 11, Moskva 3): verify or drop.
   - `MKD`, `THA`, `UGA`, `BGR`, `AUT`, `GEO` (Kvemo Kartli 43) integer rows: spot-check against sources.
   - `CHN` Shandong/Liaoning "2020 census" without counts: verify.
   - `LAT`/Chile, `KEN`, `IND`, `BGD`, `PHL`, `IDN`, `CAN`, `AUS`, `USA`, `NPL`, `ISR`, `KAZ`, `HRV`, `GUY`, `KHM`,
     `GIN`, `GNB`, `ZAF`, `NLD`: believed sourced; quick confirmation only.
2. **Registry** (`pipeline/data/sources_registry.csv`): delete rows of removed countries; rewrite rows of partial
   ones (RUS, CHN, THA, GBR, SRB, MNE, BFA, BEN, MMR, ROU, ESP, GEO, ETH, LAT) to describe exactly what is shown.
3. **Web export** (`web/prep_web.py`): basis codes — drop `m`; add `s` "Published estimate" (UCIDE Spain, ASARB
   USA); units with no figure (`p` null) → "No figure collected"; unsized communities → `m: null`.
4. **Page** (`web/site/index.html`): remove the "Mark modelled estimates" toggle and key; badge for "No figure
   collected"; labels/search skip null shares; About text: state the rule above, remove the modelled-estimates
   paragraph; community card text for unsized places (Ciudad del Este: cite the community-leader estimate only as
   attributed text, Última Hora 2026); Foz card: census 2010 count only.
5. Rebuild: `python pipeline/scripts/build_units.py` → `python web/prep_web.py` → `python web/prep_status.py` →
   `python web/project.py` → `web/topo.sh` → `python web/build_site.py` → `python web/mktest.py` →
   `node web/smoke.js` (serve `web/test` on :8765 first).
6. Show Henry a before/after list of everything removed or changed, then merge to `main`, push, republish the
   artifact (`web/site/index.html` with files map_w/map_lo/map/extra.json + units.csv, capability `downloads`).

## Follow-ups to offer afterwards (proper sourcing, not guesses)
Pakistan 2023 census district religion tables; Ghana 2021, Mozambique 2017, Suriname 2012, Sierra Leone 2015,
Liberia 2008, Chad 2009 censuses by region; Serbia 2022 all municipalities; Scotland 2022 all councils; NI 2021;
Skopje municipalities (2021 counts); Montenegro 2023 by municipality; Romania 2021 all counties; China 2020 Hui by
province; Brazil 2022 census if Islam is tabulated by municipality.

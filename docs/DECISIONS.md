# Design decisions

Why the code does what it does, in the cases where the code alone doesn't say.
Each entry exists because something was measured and the result was surprising.

---

## 1. Deduplicate by product URI, not by timestamp

The public archive serves the same acquisition reprocessed under several
processing baselines. Counting them all gives ~146 passes a year over a tile
where the orbit only allows ~73.

The two copies' `datetime` differ by **one millisecond** (15:30:09.520 vs
.519), so grouping by instant does not merge them. The stable key is the
product identifier:

    S2B_MSIL2A_20200104T152639_N0500_R025_T18PXS
    ^^^        ^^^^^^^^^^^^^^^ ^^^^^ ^^^^ ^^^^^^
    platform   sensing         baseline orbit tile

Physical identity is (platform, sensing, orbit, tile). `N####` is only the
processing version: group by the first four, keep the highest baseline.

**And the copies disagree about the clouds.** Over the field polygon, 80 % of
61 compared pairs were bit-identical; the rest differed by ~7 % of field area
on average, and on 2021-11-29 one baseline reported the field clear while the
other reported it 71.8 % covered. About 6.6 % of acquisitions cross the
usability threshold depending on version, always in the direction of the newer
processor flagging more cloud. Keeping the highest baseline therefore yields
the **conservative** estimate. Reproducible via `dedup.baseline_pairs`.

This is documented ESA behaviour — classification thresholds are re-tuned
between baselines. What would be a fault is not saying so.

## 2. A sweep that truncates silently is worse than one that crashes

The STAC continuation key is `body["next"]`, not `body["token"]`, and the link
carries `merge:false`. The first version used `"token"`: it returned 100 items
and stopped, with no error. 719 of 819 scenes would have gone missing in
silence.

`catalog.search` now compares what it downloaded against the server's declared
`context.matched` and raises if they disagree.

## 3. Read the classification band, not the scene-level cloud figure

`eo:cloud_cover` is computed over the whole tile: 110 × 110 km, 12,100 km². A
73.5 ha field is 0.006 % of that.

Measured over the polygon, 85 % of acquisitions land at an extreme — fully
clear or fully covered — against 14 % for the tile. Filtering on the scene
value produced 332 false negatives against 9 false positives across two fields:
a 37-to-1 asymmetry, all of it discarding usable data.

## 4. Two blind definitions, both published

Which classes count as blocking is a choice, and choices should be visible.

    strict   {no data, saturated, cloud shadow, cloud medium, cloud high, cirrus}
    wide     strict + cast shadow

Cast shadow is deliberately ambiguous: on flat terrain it is usually wet soil,
not shadow. **Measured, it makes no difference** — mean gap 0.0001, and not a
single acquisition changes side. The question was worth asking and the answer
is that it did not matter.

## 5. Below 25 pixels the number is flagged, not refused

With 8 pixels a percentage only moves in 12-point steps and the polygon edge
outweighs its interior. Small fields are legitimate, so `measure_view` still
returns a value — but with `warning` set and `reliable` false, and
`resolution_pct` says how coarse the figure really is.

## 6. Sentinel-1 RTC, not raw GRD

Level-1 GRD arrives in radar geometry: not geocoded, not terrain-corrected,
impossible to clip by lat/lon, and on AWS it sits in a requester-pays bucket.

RTC from the Planetary Computer is already projected to UTM at 10 m in linear
gamma0, and signs anonymously — no account, no key, no cost.

## 7. One relative orbit per series

Backscatter depends on incidence angle and look direction. Two passes on the
same day from different orbits give different values for the same crop with
nothing having changed.

**The orbit cannot be hard-coded.** Relative orbits depend on where the field
is: orbit 77 covers Zona Bananera in Magdalena, but in Urabá — Colombia's main
banana region — it does not pass at all (142 and 48 do). A fixed constant left
the radar series silently empty anywhere else. `sar.pick_orbit` picks the
best-covered orbit per field and the breakdown is printed.

## 8. Average power, not decibels

dB is logarithmic, so averaging it yields the geometric mean and biases low.
With two pixels at −20 dB and 0 dB the bias is **7.03 dB**. `sar.mean_db`
averages linear power and converts afterwards.

## 9. One container token, not one signature per file

Signing each band separately meant 2 requests × 590 scenes = 1,180 calls with
8 threads. The server returned **429** and only 54 of 590 measurements got
through — recorded as *"radar had no data here"*, a false conclusion caused by
plumbing.

The token carries `sr=c`: it is container-scoped and valid for the whole
collection. One request instead of 1,180.

## 10. A network stumble must not become a data point

The same sweep produced **0 failures one morning and 14 that afternoon**; the
errors read `Could not resolve host`. DNS, not the files.

Two layers guard against it. `net.session` retries 429 and 5xx with growing
backoff and honours `Retry-After` — but not 404, which does not improve by
insisting and would be worse hidden. And `sweep.sweep` runs a **second pass**,
serially and slowly, over whatever failed: transient trouble clears, genuinely
dead paths fail again and are then declared.

For the same reason each field is measured in isolation. A `ConnectionError`
mid-catalogue used to bring down the whole run and lose the fields already
measured; now the failure is declared, the rest continue, and the exit code
says the measurement is incomplete.

## 11. Report the uncertainty the data actually has

Ordinary least squares assumes independent observations. A radar series is not:
residual autocorrelation of 0.76 means 341 passes are worth about **47
independent observations**, and the classical standard error comes out 1.7×
too small.

`analysis.hac_trend` uses Newey-West. `analysis.change_shape` compares four
candidate shapes by BIC instead of assuming a straight line — and charges each
one for the breakpoints it has to search, or any model with cuts would always
look better than it is. On the banana-corridor field, plateau-ramp-plateau beats
the straight line by 270 BIC points, which changes the reading entirely: a ramp
looks like growth, a step between two stable levels looks like an event.

## 12. One GDAL warning, silenced only after checking

`NotGeoreferencedWarning` appeared on 9 of 602 scenes under 12 threads, though
the CRS was correct and the transform was not the identity. Control: the same
27 acquisitions measured serially and in parallel gave **identical values, 27 of
27**, histogram included. It is silenced in `scl._read_scl` alone, and
`test_measurement_is_deterministic_under_threads` guards that it stays true.

Nine false warnings per sweep hide the real ones.

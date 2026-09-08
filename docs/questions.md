# Evaluation Question Set (v1, verified)

Scope: Queens, 2024. Tables: volume, collisions, complaints_311, permits.
Tiers: L1 = single-table lookup, L2 = one-hop attribution, L3 = multi-hop
attribution. `trap` marks questions whose correct answer is "no anomaly"
or "insufficient evidence" — the agent must NOT invent a cause.
Expected answers verified via scripts/verify_answers.py on 2026-09-08.

## L1 — Lookup (5)

**Q1.** How many collisions were recorded in Queens in June 2024?
- Tables: collisions. Expected: 1,517.

**Q2.** On which dates does Northern Boulevard have traffic volume data?
- Tables: volume. Expected: 2024-06-04..06-10 and 2024-11-16..11-24.

**Q3.** What were the most common traffic-related 311 complaint types in
Queens in 2024, ranked?
- Tables: complaints_311. Expected: Street Condition (25,893), Traffic
  Signal Condition (12,020), Street Light Condition (8,571), Traffic
  (6,251), Highway Condition (1,566).

**Q4.** What was the total eastbound volume on Northern Boulevard on
2024-06-07?
- Tables: volume. Expected: 12,621.

**Q5.** How many construction permits were active on Kissena Boulevard on
2024-01-15?
- Tables: permits. Expected: 13.

## L2 — One-hop attribution (10)

**Q6.** Was traffic on Northern Boulevard unusually low on Sunday
2024-06-09? `trap`
- Expected: No. -5.3%/-8.2% vs mixed-week mean is normal Sunday pattern.
  Correct answer must cite day-of-week, not hunt for an incident.

**Q7.** Why was Northern Boulevard volume elevated on Friday 2024-06-07?
- Golden case (docs/manual_case_1.md). Expected: Friday evening travel
  pattern, medium-high confidence; collision (1 minor, 20:45, wrong
  direction of effect), construction (no covarying permit), and 311 (no
  acute complaint) explicitly ruled out.

**Q8.** 2024-11-18 (Monday) shows the highest volume in the November
window. Did a collision or incident cause it?
- Expected: No. Two zero-injury collisions late that day (19:31, 23:00,
  recorded as "NORTHERN BLVD") cannot explain all-day elevation; no 311
  complaints. Likely weekday/seasonal pattern; confidence medium.
- Note: collision records abbreviate the street name ("NORTHERN BLVD") —
  answers must survive street-name normalization.

**Q9.** During 160 Street's count window (2024-01-17..01-30), were there
any Traffic Signal Condition complaints on it? `trap`
- Expected: None found. Correct answer states the absence plainly rather
  than stretching for adjacent signals.

**Q10.** How does weekday volume compare to weekend volume on Northern
Boulevard in the June window?
- Expected: weekdays higher overall; Sunday lowest (-5.3% EB / -8.2% WB
  vs window mean). Cite numbers.

**Q11.** Was construction active on Broadway (Queens) during its count
window (2024-01-06..01-14), and of what kind?
- Tables: volume + permits. Expected: Yes, ~100 permits active, dominated
  by BUILDING OPERATION types (equipment placement, roadway/sidewalk
  occupancy); street-opening work includes rapid transit construction,
  water/gas installation, and traffic signal repair.

**Q12.** Was Saturday 2024-06-08 volume anomalous? `trap`
- Expected: mild EB elevation (+4.9%) within normal variation for a
  mixed-week baseline; no incident evidence. "No significant anomaly."

**Q13.** At what hours does Northern Boulevard peak eastbound vs
westbound, and what does the asymmetry suggest?
- Expected: WB peaks 07:00-09:00 (AM commute), EB peaks 15:00-17:00 (PM
  return) — classic directional commuter flow toward Manhattan-bound
  mornings and outbound afternoons.

**Q14.** Was any DOT paving work active on Northern Boulevard in June
2024?
- Expected: Yes — DOT IN-HOUSE PAVING permit 2024-05-08 to 2024-06-28.

**Q15.** Did the 20:45 collision on 2024-06-07 visibly reduce traffic in
the 21:00 hour? `trap`
- Expected: No visible dip (21:00 was +13.5% EB / +20.9% WB vs same-hour
  average). Honest answer: no observable effect; minor collision, likely
  cleared quickly.

## L3 — Multi-hop attribution (5)

**Q16.** Which day in the June window was most anomalous overall, and what
is the most likely explanation?
- Expected: 06-07 by combined |deviation| after accounting for day-of-week
  (a naive reading picks Sunday 06-09, which is normal weekend pattern).
  Explanation: Friday evening travel pattern (manual case 1).

**Q17.** Northern Boulevard's November window shows higher typical volume
than June. What explains the difference? `trap`
- Expected: cross-seasonal comparison of two short windows; candidate
  factors (holiday shopping, weather, school year) cannot be confirmed
  from these tables. Correct answer: "insufficient evidence to
  attribute", low confidence, list candidates.

**Q18.** Among the top-covered streets, which had the most collisions
during its own count window?
- Expected (with caveat): Northern Boulevard by far (171 under a naive
  min/max window). CAVEAT: its min/max span (06-04..11-24) includes a
  5-month gap with no sensor data, so the naive number overcounts; the
  correct method restricts to days with observed volume data. A correct
  agent answer must either use observed days or flag the discontinuity.

**Q19.** Is there a relationship between Street Condition complaints and
traffic volume on Northern Boulevard? `trap`
- Expected: with ~16 observed days, no statistically meaningful claim is
  possible. Correct answer acknowledges the data limitation.

**Q20.** Did any construction permit covary with a measurable volume
change on Northern Boulevard in June 2024?
- Expected: Several permits have date boundaries inside the window
  (gas/manhole/conduit repairs ending 06-04..06-08, refuse containers
  06-04..06-11), but none plausibly explains the observed +5-7% on
  06-07: types are curb/sidewalk-scale and the effect direction (volume
  increase) does not match construction impact. Correct answer: no
  covarying permit-based explanation; boundary permits enumerated and
  dismissed with reasons.
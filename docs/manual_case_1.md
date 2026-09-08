# Manual Case 1: Northern Boulevard, Friday 2024-06-07

## Question
Why was traffic volume on Northern Boulevard on Friday 2024-06-07 elevated
(+5.4% EB, +7.2% WB) relative to the June observation-window mean?

## Hypotheses
1. Regular Friday travel pattern (weekly seasonality)
2. Collision-induced disruption
3. Construction activity
4. Special event / induced demand
5. Data artifact (missing or duplicated sensor records)

## Evidence

### A. Hourly profile (target day vs other-day same-hour average)
- Overnight hours (00:00-03:00) were BELOW average (-12% to -27%).
- AM commute spike: WB +29.7% at 05:00, +20.5% at 06:00; EB +27.9% at 07:00.
- Midday roughly normal (±8%).
- Sustained elevation from 15:00 onward; strongest late evening:
  WB +31.2% at 22:00, +24.4% at 23:00; EB +15.9% at 19:00.
- Shape: the surplus is concentrated in evening/late-night hours, the
  signature of Friday leisure travel rather than an all-day disruption.

### B. Collisions
- Exactly one collision near Northern Blvd on the target day:
  20:45, zero injuries, "Passing Too Closely".
- Collisions suppress throughput; they cannot explain an INCREASE.
- Timing (20:45) also cannot explain elevation that began at 15:00.

### C. 311 complaints
- Six complaints, all routine Street Condition types (potholes, faded
  markings, defective hardware). No acute, day-specific incident.

### D. Construction permits
- 216 permits were active on the corridor on the target day.
- Nearly all are long-running (multi-week to multi-month) and were equally
  active on every other day in the comparison window. A factor present on
  both baseline days and the anomalous day has zero covariance with the
  anomaly and cannot explain it.
- Only 2 permits (commercial refuse containers) had date boundaries
  touching 06-07; neither plausibly increases traffic volume.

## Conclusion
Most likely cause: **regular Friday evening travel pattern**, i.e. weekly
seasonality rather than an operational incident.
**Confidence: medium-high.**
Supporting: hour-level shape matches Friday leisure profile; all incident
hypotheses ruled out.
Caveat: the 7-day baseline mixes weekdays and weekend days and contains
only one Friday, so "deviation from window mean" partly measures ordinary
day-of-week variation. A day-of-week-matched baseline would be needed to
call this day anomalous *for a Friday*.

## Ruled out
- **Collision**: wrong direction of effect (suppresses, not increases) and
  wrong timing (20:45 vs elevation from 15:00).
- **Construction**: no covariance — permits span the entire window, so they
  are part of the baseline, not a differentiator for one day.
- **311-signaled incident**: no acute complaint on the target day.
- **Data artifact**: coverage is complete (96 rows per day per direction).

## Method notes (for tool design)
1. Explanatory factors must covary with the anomaly. Long-running
   conditions cannot explain single-day deviations.
2. Effect direction matters: an evidence item that pushes the metric the
   wrong way is exculpatory, not incriminating.
3. Raw evidence must be summarized before reasoning: 216 permit rows must
   arrive as aggregates + boundary-matched details, never as a full dump.
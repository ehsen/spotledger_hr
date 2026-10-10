# Scoped final-duration rounding (default off)

Python-only capability; no migration, DocType field, fixture, or patch required.
Code deployment and site-config activation are separate steps requiring separate
approval. Deploying this code alone does not enable the feature.

Proposed site-config entry (example only; not activated):

```json
{
  "spotledger_hr_final_duration_rounding": {
    "Exact Attendance Rule Name": {
      "from_date": "2026-07-01",
      "through_date": "2026-07-31"
    }
  }
}
```

Rule names must match exactly. Both bounds are required canonical `YYYY-MM-DD`
dates, inclusive; reversed/invalid/missing bounds or malformed configuration fail
closed. Only explicitly configured `Factory Timing` rules with
`enable_overtime_rounding` equal to integer `1` or boolean `true`, interval 30
minutes and threshold 15 minutes qualify. Missing mode, string checkbox values,
other integers and other modes/settings do not qualify. Remove the entry to disable.

Eligible ordinary positive OT and deficiency are rounded separately at their final
return paths to nearest half hour, ties upward, after stabilizing duration to whole
seconds. Existing clock rounding, grace, punch selection, break handling, Friday
logic, overnight handling, suppression and gazetted early returns are untouched.
`Hours Completed` and its existing rounding helper retain their old semantics;
all default-off calculations are unchanged. No stored Attendance or payroll is
recalculated merely by deployment or activation; any regeneration is a separate gate.

## Verification limitations

DB-free tests run the real engine and controller metric mapping, replacing only
retrieval/metadata access. Fractional-required-hours summary tie and ±1-second
neighbors, malformed eligibility/configuration and cleanup are covered. A 1,536-case
default-off differential census matches the original HEAD engine. These are not
native Attendance validate/insert/reload or payroll integration tests. The isolated
`friday-policy-test.local` database test remains blocked by authentication error
1045; do not substitute fixtures on a business site or claim native integration green.

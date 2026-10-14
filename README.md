## Spotledger Hr

Frappe app to customize and override default frappe HRMS

### Optional employee payroll policies

These Python-only policies are **off by default**. Deploying this code does not
activate them, alter Employee records, recompute Attendance, or regenerate payroll.
No schema migration is required for this change. Deployment and activation are
separate operator actions; verify the actual production bench/site before either.

If separately authorized, merge the following schema into that site's existing
`site_config.json` (replace the illustrative employee keys with verified Employee
names; retain unrelated configuration and existing entries):

```json
{
  "absence_only_employee_periods": {
    "VERIFIED_ABSENCE_ONLY_EMPLOYEE": {
      "from_date": "2026-07-01",
      "through_date": "2026-07-31"
    }
  },
  "payroll_employment_end_dates": {
    "VERIFIED_CUTOFF_EMPLOYEE": "2026-07-18"
  }
}
```

Use JSON objects and valid ISO dates. `absence_only_employee_periods` is inclusive:
Attendance must fall within the interval and a salary slip's **entire** period must
fit within it. Genuine positive same-day source pairs can promote Absent to Present;
blank/stale sources cannot. Worked-day deficiency is suppressed; ordinary and
gazetted overtime pay is zero. Genuine absence remains chargeable, including the
existing rule's Friday-absence treatment. This does not create missing source data.

`payroll_employment_end_dates` is an inclusive audited payroll entitlement cutoff,
not an Employee relieving-date update. The effective attendance end is
`min(slip.end_date, cutoff)` for paid days, Friday credits, overtime and deficiency.
Opted-in paid days use the inclusive slip range, including partial periods; a
period wholly after cutoff has zero eligible days. Advances retain their original
payroll-period handling. This cutoff continues to apply to later slips until the
configuration is removed; it is not restricted to July.

After an authorized activation, clear the target site's cache and restart its
Python web/workers using the deployment's normal operations procedure so all
processes reload configuration. Read back both the deployed revision and effective
site configuration before validation. To deactivate, remove only the intended
employee entries and reload cache/processes; this does not undo saved documents.

Before any authorized saved recalculation, run rollback-only full native
Attendance and Salary Slip validation on the real employees and complete verified
sources. Check short worked days, genuine blank absences, zero OT pay, July-only
scope, the inclusive July 18 cutoff and exclusion of later Sundays/Fridays. Review
all components, advances, source completeness and an unaffected control. Do not
submit payroll on the basis of calculation-only comparisons. Existing saved
Attendance/slips are not retroactively changed by deployment or activation.

Verification for this patch: 35 relevant tests passed, including 19 existing
regressions. The broader 89-test suite is **not green**: baseline and patched runs
both had the same 3 failures and 39 errors. Real-employee full native validation
remains a post-deployment gate; local captured-source calculation checks are not
that integration proof. The root-level local evidence runner is intentionally not
part of the shipped app; synthetic native fixture tests retain their isolated-site
guards.

#### License

mit
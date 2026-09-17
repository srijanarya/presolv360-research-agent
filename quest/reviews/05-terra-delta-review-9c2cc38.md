## Verified

The claim holds for returned members, classifications, and gaps.

- Missing `members`: still yields no members and drops that cluster; now it records `malformed_member_collection`.
- Unknown adversarial revision IDs: still never affect a member; now logged per revision entry rather than per distinct ID.
- Recheck failure logging no longer includes the cluster statement.

The only observable changes are diagnostics: rejection/log counts and the all-rejected `ValueError` text. Trigger: a cluster omits `members`, or adversarial output repeats an unknown `source_id`.

## Assumed

`ClaimCluster`/`Gap` construction has no hidden logging or validation side effects beyond the supplied code.

## Defects introduced

None found.
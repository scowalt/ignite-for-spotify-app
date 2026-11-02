# Upload-secret recovery: temporary protected diagnostics

The first publication run reached source-map injection but the upload step received
an empty `SENTRY_AUTH_TOKEN` and returned 401. Registry login and all image pushes
were skipped. Both publishers are fenced; the desired new flag is false too.
No publication retry or upload is authorized by this diagnostic.

The temporary `Diagnose upload secret presence` workflow compares three paths in
one exact-head manual run:

1. A direct job bound to the protected `production` environment.
2. An equivalent reusable job with no secret declaration, matching the original path.
3. An equivalent reusable job declaring the same optional secret, without caller forwarding.

All three require the existing environment approval/main-only policy. Tokens have
no workflow permissions, no checkout/action dependency is used, and the only shell
operation tests nonempty presence and emits a constant present/absent result. The
credential is never printed, hashed or measured. No endpoint, registry or service
request is made by the jobs. There is no broad secret inheritance or repository-level
secret copy.

Interpret results before changing anything: all absent suggests storage/context;
direct present and reusable absent isolates the call boundary; declared versus
undeclared isolates declaration behavior. If all pass without a change, examine the
original run's context/timing rather than assuming the bug is fixed.

Capture evidence, repair only the verified cause, and repeat the same presence seam.
Remove these temporary diagnostic workflows after verification, or replace them with
a specifically reviewed permanent preflight. Keep an early missing-credential guard
in the real publisher. Never treat local fake-token protocol tests as evidence that
GitHub delivered a real environment secret. Publication remains a separate approval.

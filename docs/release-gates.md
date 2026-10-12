# Release gates

These are owned engineering deliverables, not claims that the entire project is blocked.

| Gate | Owner tranche | Required evidence | Current state |
| --- | --- | --- | --- |
| PostgreSQL scoped backend qualification | T1.1 | Full real-PostgreSQL migration/RLS suite passes | Implemented; local heavy admission and GitHub runner admission prevented execution |
| Durable authenticated hosted storage | T1.1–T1.3 | OIDC isolation, KMS access separation, restore and staging smoke | Planned |
| Physical workspace manifest registration | P0 program owner | PORTVS accepted repository row | [PORTVS PR #21](https://github.com/4444J99/portvs/pull/21), pending acceptance |
| Contextual de-identification | T2.2 | Synthetic attack corpus plus reviewed contextual-disclosure cases | Direct pattern scrubber only |
| Permitted student-processing configuration | T1.3, T5.1 | Explicit provider/region/retention authorization and credential reference | No real processing enabled |
| Next.js instructor workspace | T2.3 | Class intake and exception review browser tests | Synthetic workbench only |
| Real model assessment | T3.1–T3.2 | Grounded result contract and evidence checks against actual model output | Not connected |
| Semester/class context | T4.1–T4.3 | Longitudinal evidence and cohort-independence checks | Planned |
| Local and cloud routes | T5.1–T5.3 | Separate functional, recovery and qualification results | Both pending |
| Durable retention and deletion | T6.2 | Lifecycle and backup restore deletion tests | Policy calculation only |
| Automatic grade release | T6.1–T7.3 | Qualified route plus full-class pilot acceptance | Disabled |

P0 has no real upload endpoint and accepts only known synthetic fixture IDs. It must never be
exposed publicly as an authenticated instructor application. Retention dates in the demo are
previews; shutdown destroys its temporary encrypted records and ephemeral keys.

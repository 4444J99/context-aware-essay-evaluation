# Register edu essay evaluation repository in the workspace manifest

Owner: PORTVS workspace-manifest maintainer. Product owner: edu.
New private repository: https://github.com/4444J99/context-aware-essay-evaluation
Repository ID: 1416015488
Local repository: library/shelves/organvm-vi-koinonia/context-aware-essay-evaluation
Parent product: 4444J99/edu-organism, owner issue #55.
Current implementation runs in an isolated linked worktree under the new repository.

Required manifest entry:
```yaml
  - path: library/shelves/organvm-vi-koinonia/context-aware-essay-evaluation
    kind: repository
    owner_ref: 4444J99/context-aware-essay-evaluation
    residency: laptop
    repository_id: 1416015488
    remote: https://github.com/4444J99/context-aware-essay-evaluation.git
    custody_ref: refs/remotes/origin/main
    default_branch: main
```

Acceptance: exact repository identity and containment row validated and accepted through the PORTVS PR rail.
This entry grants no deletion authority. Preserve active linked worktrees and the local demo process.
Next action: prepare the single manifest-row PR, run the placement predicate, and submit the exact head.

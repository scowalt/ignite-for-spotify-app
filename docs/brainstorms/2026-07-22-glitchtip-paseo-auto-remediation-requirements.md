---
date: 2026-07-22
topic: glitchtip-paseo-auto-remediation
---

# Simple GlitchTip-to-Paseo Auto-Remediation

## Summary

Run new or reactivated Ignite GlitchTip issues through a small local controller. A Paseo coding agent fixes the issue, opens a PR with GitHub auto-merge enabled, and the controller resolves the issue and cleans up only after GitHub confirms the merge.

---

## Problem Frame

The existing remediator works outside Paseo and has left behind sessions, branches, PRs, and local state across several repositories. Its lifecycle is difficult to inspect and its automation is expensive to operate. The replacement should make remediation visible in Paseo while relying on GitHub’s existing branch protection and CI rather than building a second approval system.

---

## Actors

- A1. Operator: inspects failed work and intervenes when needed.
- A2. Local controller: polls GlitchTip, launches work, observes GitHub, resolves issues, and cleans up.
- A3. Coding agent: investigates an issue, makes and tests a fix, then opens a PR with auto-merge enabled.
- A4. GlitchTip: reports current issue status for Ignite projects 1 and 2.
- A5. GitHub: enforces required CI and merges approved auto-merge PRs.
- A6. Paseo: hosts visible agent workspaces and history.

---

## Key Flows

- F1. New issue remediation
  - **Trigger:** A post-baseline issue is first observed unresolved, or a previously observed resolved issue has newer unresolved activity.
  - **Actors:** A2, A3, A4, A5, A6
  - **Steps:** The controller records one job, creates a Paseo workspace from current `main`, and supplies bounded issue context. The coding agent fixes/tests/commits, opens one linked PR, and enables auto-merge.
  - **Outcome:** GitHub merges only after its required branch-protection checks pass.
  - **Covered by:** R1, R2, R3, R4, R5

- F2. Successful completion
  - **Trigger:** GitHub records the linked PR as merged.
  - **Actors:** A2, A4, A5, A6
  - **Steps:** The controller confirms the merged PR, resolves the still-current GlitchTip issue, archives the Paseo agent, and removes the registered workspace and branch.
  - **Outcome:** The merged fix and archived investigation remain inspectable.
  - **Covered by:** R5, R6

- F3. Failed work
  - **Trigger:** The coding agent fails, cannot find a fix, cannot open a PR, or GitHub closes/rejects the PR.
  - **Actors:** A1, A2, A3, A5, A6
  - **Steps:** The controller records a visible failed job and keeps the issue, workspace, and PR when present.
  - **Outcome:** No automatic retry, merge, resolution, or destructive cleanup occurs.
  - **Covered by:** R7, R8

- F4. Legacy cleanup
  - **Trigger:** The replacement is ready to take over.
  - **Actors:** A1, A2, A5
  - **Steps:** The controller freezes the legacy service, removes only preconfigured and positively identified legacy PRs, branches, sessions, worktrees, and local state, then verifies their absence.
  - **Outcome:** Unrelated work is untouched and the replacement can begin polling.
  - **Covered by:** R9, R10

---

## Requirements

**Intake and jobs**
- R1. Poll GlitchTip projects 1 and 2 at least once per minute.
- R2. Baseline unresolved issues at first enablement; create one job only for issues first observed after the baseline or positively observed as resolved and later reactivated.
- R3. Persist one simple job record per issue activation so a restart does not create a duplicate workspace, agent, branch, or PR.

**Remediation and merge**
- R4. Launch one clearly named Paseo coding agent from current `main` with bounded, redacted issue context and the configured Pi model/thinking level.
- R5. The coding agent may use the shared GitHub automation credential to push its branch, open one linked PR, and enable GitHub auto-merge. The credential must not bypass branch protection.
- R6. Resolve GlitchTip and archive/remove active remediation resources only after GitHub positively confirms that linked PR merged.

**Failure handling and visibility**
- R7. If agent work, PR creation, CI, or auto-merge fails, leave the issue unresolved and preserve inspectable Paseo/PR evidence.
- R8. Failed jobs never retry automatically; an operator can explicitly request a new attempt.

**Legacy cutover**
- R9. Before replacement dispatch starts, stop the legacy remediator and automatically close/delete only legacy artifacts that match its configured repository allowlist and durable marker.
- R10. Refuse legacy deletion on missing or conflicting ownership evidence; verify all targeted remote artifacts are gone before deleting associated local artifacts.

---

## Acceptance Examples

- AE1. **Covers R1, R2, R3, R4.** Given a completed baseline, when a new backend issue appears, one visible Paseo coding job starts from current `main`; later events create no second job.
- AE2. **Covers R2, R3.** Given a positively observed resolved frontend issue, when newer unresolved activity appears, exactly one new job is created after restart or repeated polls.
- AE3. **Covers R5, R6.** Given a coding agent opens a PR with auto-merge enabled, when GitHub’s required checks pass and GitHub records the merge, the controller resolves GlitchTip and removes active resources.
- AE4. **Covers R7, R8.** Given CI fails or the PR closes, when the controller observes it, the job remains failed and inspectable with no automatic retry or resolution.
- AE5. **Covers R9, R10.** Given an artifact has the configured legacy marker and repository match, when cutover runs, it is removed; an unmarked or conflicting artifact remains untouched.

---

## Success Criteria

- Every eligible issue creates at most one Paseo coding job within 90 seconds under normal capacity.
- GitHub-required CI is the sole merge gate; no PR merges when its branch protection blocks it.
- A confirmed merge resolves the corresponding current GlitchTip issue and removes active work without erasing archived Paseo history.
- Failed work remains visible, unresolved, and idle until an operator explicitly starts another attempt.
- The legacy remediator leaves no positively identified active artifact after cutover.

---

## Scope Boundaries

- No independent review agent, custom review result channel, or controller-managed merge gate.
- No credential splitting: the controller and coding agent share one GitHub automation credential that lacks branch-protection bypass authority.
- No automatic retry of a failed job or automatic rebasing of a PR.
- No replacement automation for RNGWars, nailbiter-app, or plive after their legacy artifacts are cleaned up.
- No public webhooks, production API changes, or deployment of the controller with the Ignite application.

---

## Key Decisions

- GitHub auto-merge with existing protected CI is the merge authority: it is simpler than reproducing CI and approval gates in the controller.
- One shared GitHub automation credential: it removes role-specific token management; branch protection remains the safety boundary.
- One durable job record per activation: it retains restart deduplication without a transition or remote-action ledger.
- Automated legacy cleanup remains enabled, but only exact preidentified artifacts are eligible for deletion.

---

## Dependencies / Assumptions

- GitHub auto-merge remains enabled and `backend` plus `frontend` remain required protected-branch checks.
- The shared GitHub credential can push feature branches, create PRs, and enable auto-merge but cannot bypass branch protection.
- Doppler config `prd` provides the GlitchTip token and the shared GitHub automation credential to the local controller.
- Paseo and Pi can launch `gpt-5.6-terra` with `xhigh` thinking locally.

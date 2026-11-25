# Repository review: 2026-11-15

This review organizes the completed work for source review and sharing. It does
not rerun the physical board or alter the 132-file captured-evidence bundle.

- [Attribution and license boundaries](../../THIRD_PARTY_NOTICES.md) credit Oxide
  Computer Company, Quartz contributors and the original SHA3 contribution.
- [Upstream verification](upstream-verification.json) compares all five vendored
  files with their exact pinned upstream URLs; every SHA-256 agrees.
- [Source-only evidence audit](evidence-audit.json) recomputes 48 measurement rows
  in six physical reports and checks source, manifest, resource and timing linkage.
- [Build-artifact audit](build-artifact-audit.json) additionally checks the retained
  binaries/checkpoints on the original workstation. These artifacts remain ignored.
- [Clean source-checkout audit](source-checkout-audit.json) repeats the portable audit
  and its five unit tests using only staged Git files, with no build directory.
- [Current full regression record](../verification.json) includes all seven engines,
  five integrated models, elastic adapter, software, and evidence-audit checks.
- The previous offline record and matching logs are archived here for chronology.
- [Rejected placement experiment](experiments/README.md) is archived outside the
  supported build entry points; it produced no deployed image.
- [Captured shared-card assembler](bench-environment/README.md) records the adjacent
  workspace dependency used by the accepted package.

The [reviewer guide](../../docs/review-guide.md) distinguishes large-buffer results,
short-message latency, original design goals, physical evidence, simulation,
source-only audit, and exact-build reproduction limits. Repository visibility
remains private. No binary release or upstream contribution is claimed.

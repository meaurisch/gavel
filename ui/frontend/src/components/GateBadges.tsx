// Three-tier gate badges. `null` means "tier didn't run" (e.g. no visible
// suite for the task) — shown as a muted dash, distinct from pass/fail.

export function TierBadge({ label, passed }: { label: string; passed: boolean | null }) {
  if (passed === null) {
    return <span className="badge neutral" title={`${label}: not run`}>{label} —</span>;
  }
  return (
    <span className={`badge ${passed ? "ok" : "fail"}`} title={`${label}: ${passed ? "passed" : "failed"}`}>
      {label} {passed ? "✓" : "✗"}
    </span>
  );
}

export function GateBadges({
  compilePassed,
  visiblePassed,
  hiddenPassed,
}: {
  compilePassed: boolean | null;
  visiblePassed: boolean | null;
  hiddenPassed: boolean | null;
}) {
  return (
    <span className="row" style={{ gap: "var(--space-1)" }}>
      <TierBadge label="build" passed={compilePassed} />
      <TierBadge label="visible" passed={visiblePassed} />
      <TierBadge label="hidden" passed={hiddenPassed} />
    </span>
  );
}

/** Compact B/V/H triplet for table rows — one quiet cell, not three badges. */
export function GateTriplet({
  compilePassed,
  visiblePassed,
  hiddenPassed,
}: {
  compilePassed: boolean | null;
  visiblePassed: boolean | null;
  hiddenPassed: boolean | null;
}) {
  const tiers: [string, string, boolean | null][] = [
    ["B", "build", compilePassed],
    ["V", "visible tests", visiblePassed],
    ["H", "hidden tests", hiddenPassed],
  ];
  return (
    <span className="gate-triplet" data-testid="gate-triplet">
      {tiers.map(([letter, name, passed]) => (
        <span
          key={letter}
          className={`t ${passed === null ? "none" : passed ? "pass" : "fail"}`}
          title={`${name}: ${passed === null ? "not run" : passed ? "passed" : "failed"}`}
        >
          {letter}
          {passed === null ? "–" : passed ? "✓" : "✕"}
        </span>
      ))}
    </span>
  );
}

// The gavel mark (Claude Design, docs/design/exports): mallet and handle
// reduced to two rounded bars mid-swing, one accent square. Fills come from
// tokens so the mark adapts to the dark theme exactly as the design's dark
// lockup specifies (accent square flips to #9aa4f0, glyph to #14161b).

export function GavelMark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" aria-hidden="true">
      <rect x="1" y="1" width="26" height="26" rx="6" fill="var(--color-accent)" />
      <g transform="rotate(-45 13 12)">
        <rect x="6" y="6" width="5" height="12" rx="2.5" fill="var(--color-accent-text-on)" />
        <rect x="9.5" y="10.9" width="11" height="2.2" rx="1.1" fill="var(--color-accent-text-on)" />
      </g>
      <rect x="13.5" y="21" width="9" height="2.6" rx="1.3" fill="var(--color-accent-text-on)" />
    </svg>
  );
}

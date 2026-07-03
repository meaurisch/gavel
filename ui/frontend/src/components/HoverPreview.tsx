// Generic hover/focus preview: wraps an inline anchor (usually an id chip)
// and shows a floating card on hover or keyboard focus. Pure CSS positioning,
// no portal — previews live inside scrollable containers fine at this scale.

import { useState } from "react";
import type { ReactNode } from "react";

export function HoverPreview({
  anchor,
  children,
  className,
}: {
  anchor: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(false);

  return (
    <span
      className={`preview-anchor ${className ?? ""}`}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      tabIndex={0}
    >
      {anchor}
      {open && <span className="preview-card" role="tooltip">{children}</span>}
    </span>
  );
}

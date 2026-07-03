// Generic hover/focus preview: wraps an inline anchor (usually an id chip)
// and shows a floating card on hover or keyboard focus. The card renders in
// a portal with fixed positioning so scroll containers (table wrappers,
// panes) can never clip it, and flips above the anchor when the viewport
// bottom would cut it off.

import { useLayoutEffect, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { createPortal } from "react-dom";

const CARD_WIDTH = 416; // 26rem — keep in sync with .preview-card
const GAP = 6;
const MARGIN = 8;

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
  const anchorRef = useRef<HTMLSpanElement | null>(null);
  const cardRef = useRef<HTMLSpanElement | null>(null);
  const closeTimer = useRef<number | null>(null);
  const [style, setStyle] = useState<CSSProperties>({});

  const show = () => {
    if (closeTimer.current !== null) {
      window.clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
    setOpen(true);
  };

  // Grace period so the pointer can travel from the chip into the card
  // (long task instructions scroll inside the card).
  const hide = () => {
    if (closeTimer.current !== null) window.clearTimeout(closeTimer.current);
    closeTimer.current = window.setTimeout(() => setOpen(false), 120);
  };

  useLayoutEffect(() => {
    if (!open || !anchorRef.current || !cardRef.current) return;
    const a = anchorRef.current.getBoundingClientRect();
    const cardH = cardRef.current.getBoundingClientRect().height;

    const left = Math.max(MARGIN, Math.min(a.left, window.innerWidth - CARD_WIDTH - MARGIN));
    const spaceBelow = window.innerHeight - a.bottom - GAP - MARGIN;
    const spaceAbove = a.top - GAP - MARGIN;

    let top: number;
    if (cardH <= spaceBelow || spaceBelow >= spaceAbove) {
      top = Math.min(a.bottom + GAP, window.innerHeight - Math.min(cardH, spaceBelow) - MARGIN);
    } else {
      top = Math.max(MARGIN, a.top - GAP - cardH);
    }
    setStyle({ position: "fixed", top, left, zIndex: 100 });
  }, [open]);

  return (
    <span
      ref={anchorRef}
      className={`preview-anchor ${className ?? ""}`}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
      tabIndex={0}
    >
      {anchor}
      {open &&
        createPortal(
          <span
            ref={cardRef}
            className="preview-card"
            role="tooltip"
            style={style}
            onMouseEnter={show}
            onMouseLeave={hide}
          >
            {children}
          </span>,
          document.body,
        )}
    </span>
  );
}

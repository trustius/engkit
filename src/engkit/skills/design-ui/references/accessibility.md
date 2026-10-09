# Accessibility and adaptation checklists

Apply the section for the UI type. Mark each item met-by-design, open or n/a (with a reason).
Examples are labeled and illustrative only; check the project's own conventions first.

## All types
- Every state in the spec is perceivable without color alone.
- Errors say what happened and how to fix it; no message is conveyed only by an icon or color.
- Motion is optional: honor the platform's reduced-motion setting; nothing flashes.
- Text can grow or reflow; no information is lost when it does.

## Web
- Focus order follows reading order; every control is reachable and operable by keyboard.
- Focus is visible; dialogs trap focus and return it to the trigger on close.
- Inputs have programmatic labels; errors are tied to their field and announced.
- Contrast meets the project's target (example: WCAG AA 4.5:1 text, 3:1 large text and controls).
- Layout adapts to narrow viewports and zoom (example: 320 px wide) without horizontal scroll.
- Respect reduced-motion preferences (example: the `prefers-reduced-motion` media query).

## Mobile
- Touch targets meet the platform minimum size (example: about 44 pt or 48 dp) with spacing.
- Every control has an accessible label and role for the screen reader; order matches reading.
- Support dynamic text sizes, portrait and landscape, and size classes (compact/regular).
- No gesture-only actions; offer a visible alternative control.
- Honor system reduce-motion and dark mode settings; do not rely on color alone.

## Desktop
- Full keyboard operation: tab order, shortcuts without conflicts, visible focus, Escape closes.
- Menus, toolbars and dialogs expose labels and roles to assistive technology.
- Window resizing and minimum sizes keep content reachable; support system high-contrast mode.
- Respect system text scaling and reduced-motion settings.

## CLI/TUI
- Output works at narrow terminal width (example: 80 columns); wrap or truncate with a marker.
- Usage and `--help` text document every flag; progress and diagnostics go to stderr.
- Interrupt (Ctrl-C) is a state: define what is printed, cleaned up and the exit code.
- No-color mode (examples: `NO_COLOR`, a `--no-color` flag); never encode meaning in color alone
  (add a word or symbol such as `error:`).
- Machine-readable output: offer a flag (example: `--json`) with a stable schema, data on stdout,
  diagnostics on stderr.
- Exit codes: 0 success, non-zero failures, distinct codes documented for usage errors.
- Non-interactive use: no prompt when stdin is not a terminal; provide flags for every prompt
  and a confirmation bypass for destructive actions (explicit, never the default).
- TUI: full keyboard navigation, visible focus marker, screen-reader-friendly plain mode,
  no spinner or animation when output is not a terminal or reduced motion is requested.

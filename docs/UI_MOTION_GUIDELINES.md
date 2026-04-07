# UI + Motion Guidelines (Phase 4.8)

Use this as the baseline when building new frontend views.

## Tokens

Global tokens live in `frontend/src/app/globals.css`.
Use tokenized values for:
- colors (`--color-*`)
- spacing (`--spacing-*`)
- radius (`--radius-*`)
- shadows (`--shadow-*`)
- motion (`--duration-*`, `--easing-*`)

## Shared state components

Prefer shared state primitives from `frontend/src/components/ui-state.tsx`:
- `LoadingState`
- `ErrorState`
- `EmptyState`

These provide consistent accessibility semantics (`role`, `aria-live`) and styling.

## Reusable UI primitives

Use components under `frontend/src/components/ui/` where applicable:
- `MetricCard`
- `DeltaChip`
- `ConfidenceMeter`
- `RiskPill`
- `SkeletonBlock`
- `EmptyState` (visual primitive)

## Motion rules

- Animate only `opacity` and `transform` for performance.
- Avoid animating layout properties (`height`, `width`, `margin`, `top/left`).
- Use utility classes already defined (`animate-fade-in`, `animate-slide-up`).
- Respect reduced motion (`prefers-reduced-motion` in global CSS).

## Accessibility

- Keep focus-visible outlines intact.
- Avoid color-only signaling: pair with text/icons where possible.
- Ensure state containers are announced correctly for loading/errors.

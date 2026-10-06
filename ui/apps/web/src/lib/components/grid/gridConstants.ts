/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * How long after a `dragstop` / `resizestop` a `change` event is still attributed
 * to that gesture.
 *
 * GridStack emits `change` for programmatic moves too (mounting, clamping,
 * compaction), and those must not be read as user intent — they would otherwise
 * be persisted as the dataset's preferred arrangement. The observed contract is
 * that a gesture's `change` arrives immediately after its `*stop` event, while
 * programmatic ones arrive outside any gesture; this window is the margin that
 * separates the two, not a measured latency.
 */
export const GESTURE_CHANGE_WINDOW_MS = 10;

/**
 * Fallback minimum cell used when a widget extension declares no `minW`/`minH`.
 * Only a floor for the *constraint*: the actual minimum handed to GridStack is
 * capped by the widget's own size so a deliberately small widget is never
 * inflated (see `minCellFor` in `GridWorkspace.svelte`).
 */
export const DEFAULT_MIN_CELL = 2;

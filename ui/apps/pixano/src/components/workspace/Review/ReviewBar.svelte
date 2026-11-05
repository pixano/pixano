<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Switch } from "bits-ui";
  import { Checks } from "phosphor-svelte";

  // The review of the open record: the review mode, how much is left to review, and Accept all.

  interface Props {
    active: boolean;
    /** How many annotations of the record are still to review. */
    pendingCount: number;
    /** How many of them Accept all accepts: those of the objects showing all theirs. */
    shownPendingCount: number;
    /** Whether a decision may be taken now. */
    canDecide: boolean;
    onActiveChange: (active: boolean) => void;
    onAcceptAll: () => void;
  }

  let { active, pendingCount, shownPendingCount, canDecide, onActiveChange, onAcceptAll }: Props =
    $props();

  const countText = $derived.by(() => {
    if (pendingCount === 0) return "Nothing left on this record";
    const hidden = pendingCount - shownPendingCount;
    const left = `${pendingCount} left on this record`;
    return hidden > 0 ? `${left} (${hidden} hidden)` : left;
  });

  // A click leaves the focus where it was: kept by the switch, the Enter that confirms a shape on
  // the canvas would turn the review off. Tab still reaches the switch, Space and Enter still toggle
  // it. For the same reason its title is no <label>, which would hand it the focus on a click.
  function keepFocusWhereItIs(event: MouseEvent): void {
    event.preventDefault();
  }
</script>

<div
  class="flex items-center justify-between gap-2 rounded-xl border border-border/50 bg-muted/20 px-3 py-2"
>
  <div class="flex items-center gap-2 min-w-0">
    <Switch.Root
      aria-label="Review mode"
      checked={active}
      onCheckedChange={onActiveChange}
      onmousedown={keepFocusWhereItIs}
      class="peer inline-flex h-[20px] w-[36px] shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors data-[state=checked]:bg-primary data-[state=unchecked]:bg-input"
    >
      <Switch.Thumb
        class="pointer-events-none block h-4 w-4 rounded-full bg-background shadow-lg ring-0 transition-transform data-[state=checked]:translate-x-4 data-[state=unchecked]:translate-x-0"
      />
    </Switch.Root>
    <span
      class="text-xs font-semibold uppercase tracking-wide"
      title="Show what is still to review, and fade the rest"
    >
      Review
    </span>
    <span class="text-xs text-muted-foreground truncate">{countText}</span>
  </div>
  <button
    type="button"
    class="flex-shrink-0 inline-flex items-center gap-1 h-7 px-2.5 rounded-md border border-success/30 bg-success/10 text-xs font-medium text-success transition-colors hover:bg-success/20 disabled:pointer-events-none disabled:opacity-50"
    title="Accept what is still to review on the objects shown; an object with a hidden annotation stays to review"
    disabled={shownPendingCount === 0 || !canDecide}
    onclick={onAcceptAll}
  >
    <Checks weight="bold" class="h-3.5 w-3.5" />
    Accept all
  </button>
</div>

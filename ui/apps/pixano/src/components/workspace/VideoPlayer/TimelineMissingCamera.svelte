<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // The lane of an object in a camera without a track of it: says so, and offers to arm the
  // box tool for that object in that camera.
  import { Plus } from "phosphor-svelte";

  import { TIMELINE_HEADER_WIDTH } from "$lib/timeline/timelineGeometry";
  import { cn } from "$lib/utils/styleUtils";

  interface Props {
    view: string;
    /** The object's name, for the button's description. */
    label: string;
    /** Sub-entities cannot be picked in the save form: no button for them. */
    canAdd: boolean;
    /** Why arming is not possible now (a session, the save form), or null. */
    addUnavailableReason: string | null;
    onAdd: () => void;
  }

  let { view, label, canAdd, addUnavailableReason, onAdd }: Props = $props();
</script>

<div
  class="sticky flex h-full w-max items-center gap-2"
  style:left="{TIMELINE_HEADER_WIDTH + 12}px"
>
  <span class="whitespace-nowrap text-xs text-foreground/65">Not annotated in {view}</span>
  {#if canAdd}
    <button
      type="button"
      class={cn(
        "inline-flex h-[22px] items-center gap-1 whitespace-nowrap rounded-[5px] border border-dashed border-border px-2 text-xs text-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        addUnavailableReason
          ? "cursor-default opacity-50"
          : "hover:border-foreground/40 hover:bg-accent",
      )}
      title={addUnavailableReason ?? `Draw a box of ${label} in ${view}`}
      aria-disabled={addUnavailableReason !== null}
      onpointerdown={(event) => event.stopPropagation()}
      onclick={() => {
        if (addUnavailableReason === null) onAdd();
      }}
    >
      <Plus class="size-3" weight="bold" />
      Add in this view
    </button>
  {/if}
</div>

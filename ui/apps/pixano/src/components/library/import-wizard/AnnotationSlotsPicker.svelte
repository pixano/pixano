<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { BoundingBox, Check, Polygon, SelectionBackground } from "phosphor-svelte";

  import { ANNOTATION_TOOLS } from "./rawSchema";
  import { WIZARD_CHOICE_CARD_CLASS, WIZARD_SECTION_HEADING_CLASS } from "./wizardStyles";
  import { cn } from "$lib/utils/styleUtils";

  interface Props {
    choices: string[];
    selected: string[];
    /** Slots the task cannot work without — included automatically, not toggleable. */
    locked?: string[];
  }

  let { choices, selected = $bindable(), locked = [] }: Props = $props();
  const icons: Record<string, typeof BoundingBox> = {
    bbox: BoundingBox,
    mask: SelectionBackground,
    multi_path: Polygon,
  };
  const optionalTools = $derived(
    choices.filter((slot) => !locked.includes(slot) && icons[slot] && ANNOTATION_TOOLS[slot]),
  );
  const includedTools = $derived(locked.filter((slot) => ANNOTATION_TOOLS[slot]));

  function toggle(slot: string) {
    if (locked.includes(slot)) return;
    selected = selected.includes(slot) ? selected.filter((s) => s !== slot) : [...selected, slot];
  }
</script>

<fieldset class="annotation-tools min-w-0 space-y-3">
  <legend class={WIZARD_SECTION_HEADING_CLASS}>Annotation tools</legend>
  {#if optionalTools.length}
    <div class="tool-options" style:--tool-columns={Math.min(optionalTools.length, 3)}>
      {#each optionalTools as slot (slot)}
        {@const tool = ANNOTATION_TOOLS[slot]}
        {@const Icon = icons[slot]}
        {@const active = selected.includes(slot)}
        <button
          type="button"
          role="checkbox"
          aria-checked={active}
          aria-label={tool.label}
          title={tool.description}
          class={cn(
            WIZARD_CHOICE_CARD_CLASS,
            "tool-choice relative flex min-h-[76px] min-w-0 flex-col items-center justify-center gap-2 px-3 py-3 text-center",
            active
              ? "border-primary/50 bg-primary/5 ring-1 ring-primary/10"
              : "border-border/70 bg-card hover:border-primary/30 hover:bg-surface-2",
          )}
          onclick={() => toggle(slot)}
        >
          <Icon
            weight="regular"
            class={cn("tool-icon h-6 w-6", active ? "text-primary" : "text-muted-foreground")}
          />
          <span class="tool-label text-[13px] font-medium leading-4 text-foreground">
            {tool.label}
          </span>
          {#if active}
            <Check weight="bold" class="absolute right-2 top-2 h-3 w-3 text-primary" />
          {/if}
        </button>
      {/each}
    </div>
  {/if}
  {#if includedTools.length}
    <div class="flex flex-wrap items-center gap-x-2 gap-y-1.5 text-xs text-muted-foreground">
      <span>Included</span>
      {#each includedTools as slot (slot)}
        <span
          class="inline-flex items-center gap-1.5 rounded-md bg-surface-2 px-2 py-1"
          title={ANNOTATION_TOOLS[slot].description}
        >
          <Check weight="bold" class="h-3 w-3" />
          {ANNOTATION_TOOLS[slot].label}
        </span>
      {/each}
    </div>
  {/if}
</fieldset>

<style>
  .annotation-tools {
    container: annotation-tools / inline-size;
  }

  .tool-options {
    display: grid;
    grid-template-columns: repeat(var(--tool-columns), minmax(0, 1fr));
    gap: 0.5rem;
  }

  @container annotation-tools (max-width: 419px) {
    .tool-choice {
      padding: 0.5rem;
    }

    .tool-choice :global(.tool-icon) {
      width: 1.25rem;
      height: 1.25rem;
    }

    .tool-label {
      font-size: 0.75rem;
    }
  }
</style>

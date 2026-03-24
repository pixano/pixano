<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Popover } from "bits-ui";
  import { Keyboard } from "phosphor-svelte";

  interface Props {
    isVideo?: boolean;
  }

  let { isVideo = false }: Props = $props();

  type Shortcut = { keys: string[]; action: string };
  type ShortcutCategory = { title: string; shortcuts: Shortcut[] };

  const generalShortcuts: ShortcutCategory = {
    title: "General",
    shortcuts: [
      { keys: ["Esc"], action: "Switch to Pan tool" },
      { keys: ["Delete", "Backspace"], action: "Delete selected point" },
      { keys: ["Ctrl+S", "⌘+S"], action: "Save all annotations" },
      { keys: ["Alt (hold)"], action: "Peek at existing annotations" },
    ],
  };

  const polygonShortcuts: ShortcutCategory = {
    title: "Polygon / Polyline",
    shortcuts: [
      { keys: ["P"], action: "Activate Polygon tool" },
      { keys: ["L"], action: "Activate Polyline tool" },
      { keys: ["N"], action: "Finish sub-path (polyline)" },
      { keys: ["Enter"], action: "Validate shape" },
      { keys: ["Esc"], action: "Cancel current path" },
    ],
  };

  const brushShortcuts: ShortcutCategory = {
    title: "Brush Tool",
    shortcuts: [
      { keys: ["B"], action: "Activate Brush tool" },
      { keys: ["X"], action: "Toggle Draw / Erase" },
      { keys: ["Q", "["], action: "Decrease brush size" },
      { keys: ["E", "]"], action: "Increase brush size" },
      { keys: ["S", "Enter"], action: "Save brush mask" },
    ],
  };

  const bboxShortcuts: ShortcutCategory = {
    title: "Bounding Box",
    shortcuts: [
      { keys: ["R"], action: "Activate Bounding Box tool" },
      { keys: ["Enter"], action: "Validate bounding box" },
    ],
  };

  const smartSegmentationShortcuts: ShortcutCategory = {
    title: "Smart Segmentation",
    shortcuts: [
      { keys: ["W"], action: "Activate Smart Segmentation" },
      { keys: ["X"], action: "Toggle + / \u2212 point prompt" },
      { keys: ["R"], action: "Box prompt" },
      { keys: ["Enter"], action: "Validate segmentation mask" },
    ],
  };

  const fusionShortcuts: ShortcutCategory = {
    title: "Fusion Tool",
    shortcuts: [
      { keys: ["Esc"], action: "Abort fusion" },
      { keys: ["S", "Enter"], action: "Validate fusion" },
    ],
  };

  const videoShortcuts: ShortcutCategory = {
    title: "Video Controls",
    shortcuts: [
      { keys: ["Space"], action: "Play / Pause" },
      { keys: ["\u2192", "D"], action: "Next frame" },
      { keys: ["\u2190", "A"], action: "Previous frame" },
    ],
  };

  const navigationShortcuts: ShortcutCategory = {
    title: "Navigation",
    shortcuts: [
      { keys: ["Shift+\u2192", "Shift+D"], action: "Next item" },
      { keys: ["Shift+\u2190", "Shift+A"], action: "Previous item" },
    ],
  };

  // Columns grouped semantically: Global | Shape tools | Painting & AI
  let leftColumn = $derived([
    generalShortcuts,
    navigationShortcuts,
    ...(isVideo ? [videoShortcuts] : []),
  ]);
  let centerColumn = $derived([bboxShortcuts, polygonShortcuts]);
  let rightColumn = $derived([
    brushShortcuts,
    smartSegmentationShortcuts,
    ...(isVideo ? [fusionShortcuts] : []),
  ]);
</script>

{#snippet categoryBlock(category: ShortcutCategory)}
  <div class="space-y-1.5">
    <div class="text-xs font-medium text-muted-foreground/70 uppercase tracking-wide">
      {category.title}
    </div>
    {#each category.shortcuts as shortcut}
      <div class="flex items-center justify-between text-xs gap-2">
        <span class="text-muted-foreground">{shortcut.action}</span>
        <div class="flex items-center gap-1 shrink-0">
          {#each shortcut.keys as key, i}
            {#if i > 0}
              <span class="text-muted-foreground/50">/</span>
            {/if}
            <kbd
              class="min-w-[1.5rem] px-1.5 py-0.5 text-center text-[11px] font-mono rounded border border-border/60 bg-muted/50 text-muted-foreground"
            >
              {key}
            </kbd>
          {/each}
        </div>
      </div>
    {/each}
  </div>
{/snippet}

<Popover.Root>
  <Popover.Trigger
    type="button"
    class="h-7 w-7 inline-flex items-center justify-center rounded-md text-foreground hover:bg-accent/60 transition-all duration-200"
    title="Keyboard Shortcuts"
  >
    <Keyboard class="h-4.5 w-4.5" />
  </Popover.Trigger>
  <Popover.Content
    class="w-[44rem] p-5 bg-popover backdrop-blur-xl border border-border rounded-lg shadow-xl"
  >
    <div class="text-sm font-medium text-foreground mb-4">Keyboard Shortcuts</div>
    <div class="grid grid-cols-3 gap-10">
      <div class="space-y-3">
        {#each leftColumn as category}
          {@render categoryBlock(category)}
        {/each}
      </div>
      <div class="space-y-3">
        {#each centerColumn as category}
          {@render categoryBlock(category)}
        {/each}
      </div>
      <div class="space-y-3">
        {#each rightColumn as category}
          {@render categoryBlock(category)}
        {/each}
      </div>
    </div>
  </Popover.Content>
</Popover.Root>

<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Settings } from "lucide-svelte";

  import { Popover } from "bits-ui";

  import { brushSettings } from "$lib/stores/workspaceStores.svelte";

  function onBrushRadiusInput(e: Event) {
    const value = +(e.target as HTMLInputElement).value;
    brushSettings.update((s) => ({ ...s, brushRadius: value }));
  }

  function onLazyRadiusInput(e: Event) {
    const value = +(e.target as HTMLInputElement).value;
    brushSettings.update((s) => ({ ...s, lazyRadius: value }));
  }

  function onFrictionInput(e: Event) {
    const value = +(e.target as HTMLInputElement).value;
    brushSettings.update((s) => ({ ...s, friction: value / 100 }));
  }
</script>

<Popover.Root>
  <Popover.Trigger
    type="button"
    class="h-7 w-7 inline-flex items-center justify-center rounded-md text-foreground hover:bg-accent/60 transition-all duration-200"
    title="Brush Settings"
  >
    <Settings class="h-4.5 w-4.5" />
  </Popover.Trigger>
  <Popover.Content class="w-64 p-4 space-y-4">
    <div class="text-sm font-medium text-foreground mb-2">Brush Settings</div>

    <div class="space-y-1.5">
      <div class="flex justify-between text-xs text-muted-foreground">
        <span>Brush Radius</span>
        <span>{brushSettings.value.brushRadius}px</span>
      </div>
      <input
        type="range"
        min="1"
        max="100"
        step="1"
        value={brushSettings.value.brushRadius}
        oninput={onBrushRadiusInput}
        class="w-full h-1.5 bg-secondary rounded-full appearance-none cursor-pointer accent-primary"
      />
    </div>

    <div class="space-y-1.5">
      <div class="flex justify-between text-xs text-muted-foreground">
        <span>Lazy Radius</span>
        <span>{brushSettings.value.lazyRadius}px</span>
      </div>
      <input
        type="range"
        min="0"
        max="150"
        step="1"
        value={brushSettings.value.lazyRadius}
        oninput={onLazyRadiusInput}
        class="w-full h-1.5 bg-secondary rounded-full appearance-none cursor-pointer accent-primary"
      />
    </div>

    <div class="space-y-1.5">
      <div class="flex justify-between text-xs text-muted-foreground">
        <span>Friction</span>
        <span>{Math.round(brushSettings.value.friction * 100)}%</span>
      </div>
      <input
        type="range"
        min="0"
        max="100"
        step="1"
        value={Math.round(brushSettings.value.friction * 100)}
        oninput={onFrictionInput}
        class="w-full h-1.5 bg-secondary rounded-full appearance-none cursor-pointer accent-primary"
      />
    </div>
  </Popover.Content>
</Popover.Root>

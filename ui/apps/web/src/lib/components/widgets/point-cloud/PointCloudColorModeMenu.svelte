<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Check, Palette } from "lucide-svelte";

  import * as DropdownMenu from "$lib/components/ui/dropdown-menu/index.js";
  import type { PointCloudColorSource } from "$lib/pointcloud/coloring/colorMode.js";
  import { COLOR_MODES_3D } from "$lib/pointcloud/coloring/registry.js";

  interface Props {
    activeModeId: string;
    onSelectMode: (id: string) => void;
    /**
     * The cloud being coloured, so each mode can say whether it applies. Null
     * before the cloud has loaded — every entry is then disabled rather than
     * offering a choice that would silently do nothing.
     */
    source: PointCloudColorSource | null;
  }

  let { activeModeId, onSelectMode, source }: Props = $props();

  /**
   * Availability per mode, asked of the modes themselves. Recomputed when the
   * source changes (a record switch brings a different cloud and different
   * cameras), never cached across one.
   */
  const availability = $derived(
    COLOR_MODES_3D.map((mode) => ({
      mode,
      reason: source
        ? (mode.unavailableReason?.(source) ?? null)
        : "Waiting for the point cloud to load",
    })),
  );

  const activeMode = $derived(COLOR_MODES_3D.find((mode) => mode.id === activeModeId));
</script>

<DropdownMenu.Root>
  <DropdownMenu.Trigger
    title={activeMode ? `Point colours: ${activeMode.label}` : "Point colours"}
    aria-label="Point cloud colour mode"
    class="flex items-center gap-1 rounded p-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground"
  >
    <Palette class="h-3.5 w-3.5" />
  </DropdownMenu.Trigger>

  <!-- Anchored by its end: the trigger sits at the toolbar's right edge, so a
       menu growing rightwards would spill out of the widget and over the
       inspector panel. -->
  <DropdownMenu.Content class="w-56" align="end">
    <DropdownMenu.Label>Point colours</DropdownMenu.Label>
    <DropdownMenu.Separator />

    {#each availability as { mode, reason } (mode.id)}
      <!-- A mode that cannot run stays visible and disabled, carrying its own
           reason: vanishing would read as a missing feature, while "this record
           has no calibrated camera" teaches what the mode needs. -->
      <DropdownMenu.Item
        disabled={reason !== null}
        title={reason ?? mode.label}
        onSelect={() => onSelectMode(mode.id)}
      >
        <mode.icon class="h-4 w-4" />
        <span class="flex-1 truncate">{mode.label}</span>
        {#if mode.id === activeModeId}
          <Check class="h-3.5 w-3.5" />
        {/if}
      </DropdownMenu.Item>
    {/each}
  </DropdownMenu.Content>
</DropdownMenu.Root>

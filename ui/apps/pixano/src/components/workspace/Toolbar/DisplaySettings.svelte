<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Popover, Slider as SliderPrimitive, Switch } from "bits-ui";
  import { Sliders } from "phosphor-svelte";

  import { filters, imageSmoothing, itemMetas } from "$lib/stores/workspaceStores.svelte";
  import { WorkspaceType } from "$lib/types/dataset";
  import { IconButton } from "$lib/ui";

  // Display adjustments are canvas TOOLS (not record data): they live in the toolbar and
  // drive the same global stores the canvas filter pipeline consumes.
  const isVideo = $derived(itemMetas.value?.type === WorkspaceType.VIDEO);
  const safeItemColor = $derived(itemMetas.value?.color ?? "rgb");
  const safeItemFormat = $derived(itemMetas.value?.format ?? "8bit");

  let open = $state(false);
  let combineChannels = $state(false);

  const thumbClass =
    "block h-3.5 w-3.5 rounded-full border-2 border-primary bg-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
  const sliderRootClass = "relative flex w-full touch-none select-none items-center";
  const trackClass = "relative h-1.5 w-full grow overflow-hidden rounded-full bg-secondary";
  const rangeClass = "absolute h-full bg-primary";
  const switchRootClass =
    "peer inline-flex h-[24px] w-[44px] shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring data-[state=checked]:bg-primary data-[state=unchecked]:bg-input";
  const switchThumbClass =
    "pointer-events-none block h-5 w-5 rounded-full bg-background shadow-lg ring-0 transition-transform data-[state=checked]:translate-x-5 data-[state=unchecked]:translate-x-0";
  const numberInputClass =
    "h-8 w-16 rounded-lg border border-input bg-background text-center text-xs tabular-nums focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
</script>

<Popover.Root bind:open>
  <Popover.Trigger>
    {#snippet child({ props })}
      <span {...props}>
        <IconButton tooltipContent="Display settings" selected={open} class="h-8 w-8 rounded-lg">
          <Sliders class="h-4.5 w-4.5" />
        </IconButton>
      </span>
    {/snippet}
  </Popover.Trigger>
  <Popover.Portal>
    <Popover.Content
      sideOffset={10}
      class="z-50 w-80 space-y-4 rounded-2xl border border-border/50 bg-popover/95 p-4 text-popover-foreground shadow-elevation-2 backdrop-blur-md"
    >
      <!-- General -->
      <section class="space-y-2">
        <h4 class="text-label text-left">General</h4>
        <div class="flex w-full items-center justify-between">
          <label for="smoothing" class="cursor-pointer select-none text-sm">Image smoothing</label>
          <Switch.Root id="smoothing" bind:checked={imageSmoothing.value} class={switchRootClass}>
            <Switch.Thumb class={switchThumbClass} />
          </Switch.Root>
        </div>

        {#if !isVideo}
          <div class="flex w-full items-center justify-between">
            <label for="equalizer" class="cursor-pointer select-none text-sm">
              Equalize histogram
            </label>
            <Switch.Root
              id="equalizer"
              bind:checked={filters.value.equalizeHistogram}
              class={switchRootClass}
            >
              <Switch.Thumb class={switchThumbClass} />
            </Switch.Root>
          </div>
          <div class="flex items-center gap-2 text-sm">
            <span class="w-20 shrink-0">Brightness</span>
            <SliderPrimitive.Root
              type="single"
              min={-0.5}
              max={0.5}
              step={0.01}
              value={filters.value.brightness}
              onValueChange={(v: number) => {
                filters.value.brightness = v;
              }}
              class={sliderRootClass}
            >
              <span class={trackClass}>
                <SliderPrimitive.Range class={rangeClass} />
              </span>
              <SliderPrimitive.Thumb index={0} class={thumbClass} />
            </SliderPrimitive.Root>
            <span class="w-10 shrink-0 text-right text-xs tabular-nums">
              {Math.round(filters.value.brightness * 100 + 50)}%
            </span>
          </div>
          <div class="flex items-center gap-2 text-sm">
            <span class="w-20 shrink-0">Contrast</span>
            <SliderPrimitive.Root
              type="single"
              min={-50}
              max={50}
              step={1}
              value={filters.value.contrast}
              onValueChange={(v: number) => {
                filters.value.contrast = v;
              }}
              class={sliderRootClass}
            >
              <span class={trackClass}>
                <SliderPrimitive.Range class={rangeClass} />
              </span>
              <SliderPrimitive.Thumb index={0} class={thumbClass} />
            </SliderPrimitive.Root>
            <span class="w-10 shrink-0 text-right text-xs tabular-nums">
              {Math.round(filters.value.contrast + 50)}%
            </span>
          </div>
        {/if}
      </section>

      {#if !isVideo}
        <!-- Channels -->
        <section class="space-y-2 border-t border-border/50 pt-3">
          <h4 class="text-label text-left">Channels</h4>
          {#if safeItemColor === "rgba"}
            <div class="flex w-full items-center justify-between">
              <label for="grayscale" class="cursor-pointer select-none text-sm">
                Combine RGB channels
              </label>
              <Switch.Root id="grayscale" bind:checked={combineChannels} class={switchRootClass}>
                <Switch.Thumb class={switchThumbClass} />
              </Switch.Root>
            </div>
          {/if}
          {#if combineChannels || safeItemColor === "grayscale"}
            <div class="flex items-center gap-2 text-center text-sm">
              <span class="w-4 shrink-0 text-left">G</span>
              <span class="w-8 shrink-0 text-xs tabular-nums">{filters.value.redRange[0]}</span>
              <SliderPrimitive.Root
                type="multiple"
                min={0}
                max={255}
                step={1}
                value={filters.value.redRange}
                onValueChange={(v: number[]) => {
                  filters.value.redRange = v;
                  filters.value.blueRange = v;
                  filters.value.greenRange = v;
                }}
                class={sliderRootClass}
              >
                <span class={trackClass}>
                  <SliderPrimitive.Range class={rangeClass} />
                </span>
                <SliderPrimitive.Thumb index={0} class={thumbClass} />
                <SliderPrimitive.Thumb index={1} class={thumbClass} />
              </SliderPrimitive.Root>
              <span class="w-8 shrink-0 text-xs tabular-nums">{filters.value.redRange[1]}</span>
            </div>
          {:else}
            <!-- Channel letters keep their literal channel colors: data encoding, not chrome. -->
            <div class="flex items-center gap-2 text-center text-sm text-red-500">
              <span class="w-4 shrink-0 text-left">R</span>
              <span class="w-8 shrink-0 text-xs tabular-nums">{filters.value.redRange[0]}</span>
              <SliderPrimitive.Root
                type="multiple"
                min={0}
                max={255}
                step={1}
                value={filters.value.redRange}
                onValueChange={(v: number[]) => {
                  filters.value.redRange = v;
                }}
                class={sliderRootClass}
              >
                <span class={trackClass}>
                  <SliderPrimitive.Range class={rangeClass} />
                </span>
                <SliderPrimitive.Thumb index={0} class={thumbClass} />
                <SliderPrimitive.Thumb index={1} class={thumbClass} />
              </SliderPrimitive.Root>
              <span class="w-8 shrink-0 text-xs tabular-nums">{filters.value.redRange[1]}</span>
            </div>
            <div class="flex items-center gap-2 text-center text-sm text-green-500">
              <span class="w-4 shrink-0 text-left">G</span>
              <span class="w-8 shrink-0 text-xs tabular-nums">{filters.value.greenRange[0]}</span>
              <SliderPrimitive.Root
                type="multiple"
                min={0}
                max={255}
                step={1}
                value={filters.value.greenRange}
                onValueChange={(v: number[]) => {
                  filters.value.greenRange = v;
                }}
                class={sliderRootClass}
              >
                <span class={trackClass}>
                  <SliderPrimitive.Range class={rangeClass} />
                </span>
                <SliderPrimitive.Thumb index={0} class={thumbClass} />
                <SliderPrimitive.Thumb index={1} class={thumbClass} />
              </SliderPrimitive.Root>
              <span class="w-8 shrink-0 text-xs tabular-nums">{filters.value.greenRange[1]}</span>
            </div>
            <div class="flex items-center gap-2 text-center text-sm text-blue-500">
              <span class="w-4 shrink-0 text-left">B</span>
              <span class="w-8 shrink-0 text-xs tabular-nums">{filters.value.blueRange[0]}</span>
              <SliderPrimitive.Root
                type="multiple"
                min={0}
                max={255}
                step={1}
                value={filters.value.blueRange}
                onValueChange={(v: number[]) => {
                  filters.value.blueRange = v;
                }}
                class={sliderRootClass}
              >
                <span class={trackClass}>
                  <SliderPrimitive.Range class={rangeClass} />
                </span>
                <SliderPrimitive.Thumb index={0} class={thumbClass} />
                <SliderPrimitive.Thumb index={1} class={thumbClass} />
              </SliderPrimitive.Root>
              <span class="w-8 shrink-0 text-xs tabular-nums">{filters.value.blueRange[1]}</span>
            </div>
          {/if}
        </section>

        {#if safeItemFormat === "16bit"}
          <!-- 16-bit range -->
          <section class="space-y-2 border-t border-border/50 pt-3">
            <h4 class="text-label text-left">16-bit range</h4>
            <div class="flex items-center gap-2 text-sm">
              <input
                type="number"
                aria-label="16-bit range minimum"
                class={numberInputClass}
                bind:value={filters.value.u16BitRange[0]}
              />
              <SliderPrimitive.Root
                type="multiple"
                min={0}
                max={65535}
                step={1}
                value={filters.value.u16BitRange}
                onValueChange={(v: number[]) => {
                  filters.value.u16BitRange = v;
                }}
                class={sliderRootClass}
              >
                <span class={trackClass}>
                  <SliderPrimitive.Range class={rangeClass} />
                </span>
                <SliderPrimitive.Thumb index={0} class={thumbClass} />
                <SliderPrimitive.Thumb index={1} class={thumbClass} />
              </SliderPrimitive.Root>
              <input
                type="number"
                aria-label="16-bit range maximum"
                class={numberInputClass}
                bind:value={filters.value.u16BitRange[1]}
              />
            </div>
          </section>
        {/if}
      {/if}
    </Popover.Content>
  </Popover.Portal>
</Popover.Root>

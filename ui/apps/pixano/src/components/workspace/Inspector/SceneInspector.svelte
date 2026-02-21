<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // External library imports

  // Internal library imports
  import { Pencil } from "lucide-svelte";
  import { Slider as SliderPrimitive } from "bits-ui";

  import { Switch } from "bits-ui";

  import { IconButton, Image, SequenceFrame, View } from "$lib/ui";

  import { datasetSchema } from "$lib/stores/appStores.svelte";
  import { createFeature } from "$lib/utils/featureMapping";
  import { saveTo } from "$lib/utils/saveItemUtils";
  // Local imports
  import {
    filters,
    imageSmoothing,
    itemMetas,
    mediaViews,
  } from "$lib/stores/workspaceStores.svelte";
  import { currentFrameIndex } from "$lib/stores/videoStores.svelte";
  import type { ItemsMeta } from "$lib/types/workspace";
  import UpdateFeatureInputs from "../Features/UpdateFeatureInputs.svelte";

  type ViewMeta = {
    url: string | undefined;
    width: number;
    height: number;
    format: string;
    id: string;
    view: string;
  };

  // Component state variables
  let isEditing: boolean = $state(false);
  let combineChannels: boolean = $state(false);

  const viewData = $derived.by(() => {
    const views = Object.values(mediaViews.value || {});
    let nextIsVideo = false;
    const nextViewMeta = views.map((view: View | View[]) => {
      let image: Image | SequenceFrame | undefined;
      if (Array.isArray(view)) {
        nextIsVideo = true;
        image = view[currentFrameIndex.value] as SequenceFrame | undefined;
      } else {
        image = view as Image;
      }
      return image
        ? {
            url: image.data.url,
            width: image.data.width,
            height: image.data.height,
            format: image.data.format,
            id: image.id,
            view: image.table_info.name,
          }
        : {
            url: undefined,
            width: 0,
            height: 0,
            format: "",
            id: "",
            view: "",
          };
    });
    return { isVideo: nextIsVideo, viewMeta: nextViewMeta };
  });

  const features = $derived.by(() => {
    const metas = itemMetas.value;
    if (!metas?.item) return [];
    if (!datasetSchema.value?.schemas?.[metas.item.table_info.name]) return [];
    return createFeature(metas.item, datasetSchema.value);
  });

  const safeItemColor = $derived(itemMetas.value?.color ?? "rgb");
  const safeItemFormat = $derived(itemMetas.value?.format ?? "8bit");

  /**
   * Toggle the editing state.
   */
  const handleEditIconClick = (): void => {
    isEditing = !isEditing;
  };

  /**
   * Update the text input change for a specific property in itemMetas.
   *
   * @param value - The new value for the property.
   * @param propertyName - The name of the property to update.
   */
  const handleTextInputChange = (value: string | boolean | number, propertyName: string) => {
    itemMetas.update((oldMetas) => {
      if (!oldMetas) return oldMetas;
      const newMetas: ItemsMeta = { ...oldMetas };
      newMetas.item.data[propertyName] = value;
      saveTo("update", newMetas.item);
      return newMetas;
    });
  };

  const thumbClass =
    "block h-3.5 w-3.5 rounded-full border-2 border-primary bg-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
  const sliderRootClass = "relative flex w-full touch-none select-none items-center";
  const trackClass = "relative h-1.5 w-full grow overflow-hidden rounded-full bg-secondary";
  const rangeClass = "absolute h-full bg-primary";
</script>

<!-- Features Section -->
<div class="p-4 pb-8 text-foreground">
  <h3 class="uppercase font-medium h-10">
    <span>Features</span>
    <IconButton
      selected={isEditing}
      onclick={handleEditIconClick}
      tooltipContent="Edit scene features"
    >
      <Pencil class="h-4" />
    </IconButton>
  </h3>
  <div class="mx-4">
    <UpdateFeatureInputs
      featureClass="main"
      {features}
      {isEditing}
      saveInputChange={handleTextInputChange}
    />
  </div>
</div>

<!-- Item Meta Information Section -->
<div class="p-4 pb-8 border-b-2 border-b-border text-foreground">
  <h3 class="uppercase font-medium h-10 flex items-center">Views</h3>
  {#each viewData.viewMeta as meta}
    <h2 class="font-medium h-10 flex items-center truncate" title="{meta.id} ({meta.view})">
      {meta.id} ({meta.view})
    </h2>
    <div class="mx-4">
      <div class="grid gap-4 grid-cols-[150px_auto]">
        <p class="font-medium">URL</p>
        <p class="truncate" title={meta.url}>{meta.url}</p>
      </div>
      <div class="grid gap-4 grid-cols-[150px_auto]">
        <p class="font-medium">Width</p>
        <p>{meta.width}</p>
      </div>
      <div class="grid gap-4 grid-cols-[150px_auto]">
        <p class="font-medium">Height</p>
        <p>{meta.height}</p>
      </div>
      <div class="grid gap-4 grid-cols-[150px_auto]">
        <p class="font-medium">Format</p>
        <p>{meta.format}</p>
      </div>
    </div>
  {/each}
</div>

<!-- Filters Section -->
<div class="p-4 pb-8 text-foreground font-medium">
  <h3 class="uppercase font-medium h-10">FILTERS</h3>

  <!-- General Filters -->
  <div class="border border-border rounded py-2 px-4 text-sm">
    <h4 class="uppercase font-medium h-6 text-muted-foreground">GENERAL</h4>
    <!-- Image Smoothing -->
    <div class="w-full my-1 flex items-center justify-between">
      <label for="smoothing" class="select-none cursor-pointer">Image smoothing</label>
      <Switch.Root id="smoothing" bind:checked={imageSmoothing.value}
        class="peer inline-flex h-[24px] w-[44px] shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors data-[state=checked]:bg-primary data-[state=unchecked]:bg-input"
      >
        <Switch.Thumb
          class="pointer-events-none block h-5 w-5 rounded-full bg-background shadow-lg ring-0 transition-transform data-[state=checked]:translate-x-5 data-[state=unchecked]:translate-x-0"
        />
      </Switch.Root>
    </div>

    {#if !viewData.isVideo}
      <!-- Histogram Equalizer -->
      <div class="w-full my-1 flex items-center justify-between">
        <label for="equalizer" class="select-none cursor-pointer">Equalize histogram</label>
        <Switch.Root id="equalizer" bind:checked={filters.value.equalizeHistogram}
          class="peer inline-flex h-[24px] w-[44px] shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors data-[state=checked]:bg-primary data-[state=unchecked]:bg-input"
        >
          <Switch.Thumb
            class="pointer-events-none block h-5 w-5 rounded-full bg-background shadow-lg ring-0 transition-transform data-[state=checked]:translate-x-5 data-[state=unchecked]:translate-x-0"
          />
        </Switch.Root>
      </div>
      <!-- Brightness -->
      <div class="flex items-center">
        <label for="brightness" class="w-20 pb-1">Brightness</label>
        <div class="grow text-xs">
          <SliderPrimitive.Root
            type="single"
            min={-0.5}
            max={0.5}
            step={0.01}
            value={filters.value.brightness}
            onValueChange={(v) => {
              filters.value.brightness = v;
            }}
            class={sliderRootClass}
          >
            <span class={trackClass}>
              <SliderPrimitive.Range class={rangeClass} />
            </span>
            <SliderPrimitive.Thumb index={0} class={thumbClass} />
          </SliderPrimitive.Root>
        </div>
        <span class="w-8">{Math.round(filters.value.brightness * 100 + 50)}%</span>
      </div>

      <!-- Contrast -->
      <div class="flex items-center text-sm">
        <label for="contrast" class="w-20 pb-1">Contrast</label>
        <div class="grow text-xs">
          <SliderPrimitive.Root
            type="single"
            min={-50}
            max={50}
            step={1}
            value={filters.value.contrast}
            onValueChange={(v) => {
              filters.value.contrast = v;
            }}
            class={sliderRootClass}
          >
            <span class={trackClass}>
              <SliderPrimitive.Range class={rangeClass} />
            </span>
            <SliderPrimitive.Thumb index={0} class={thumbClass} />
          </SliderPrimitive.Root>
        </div>
        <span class="w-8">{Math.round(filters.value.contrast + 50)}%</span>
      </div>
    {/if}
  </div>

  {#if !viewData.isVideo}
    <!-- Color Channels Filters -->
    <div class="mt-4 border border-border rounded py-2 px-4 text-sm">
      <h4 class="uppercase font-medium h-6 text-muted-foreground">CHANNELS</h4>

      {#if safeItemColor === "rgba"}
        <div class="w-full my-1 flex items-center justify-between">
          <label for="grayscale" class="select-none cursor-pointer text-sm">
            Combine RGB channels
          </label>
          <Switch.Root id="grayscale" bind:checked={combineChannels}
            class="peer inline-flex h-[24px] w-[44px] shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors data-[state=checked]:bg-primary data-[state=unchecked]:bg-input"
          >
            <Switch.Thumb
              class="pointer-events-none block h-5 w-5 rounded-full bg-background shadow-lg ring-0 transition-transform data-[state=checked]:translate-x-5 data-[state=unchecked]:translate-x-0"
            />
          </Switch.Root>
        </div>
      {/if}
      {#if combineChannels || safeItemColor === "grayscale"}
        <!-- Grayscale -->
        <div class="flex items-center text-sm text-center">
          <span class="text-left w-4">G</span>
          <span class="w-8">{filters.value.redRange[0]}</span>
          <div class="grow text-xs">
            <SliderPrimitive.Root
              type="multiple"
              min={0}
              max={255}
              step={1}
              value={filters.value.redRange}
              onValueChange={(v) => {
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
          </div>
          <span class="w-8">{filters.value.redRange[1]}</span>
        </div>
      {:else}
        <!-- Red -->
        <div class="flex items-center text-sm text-center text-red-500">
          <span class="text-left w-4">R</span>
          <span class="w-8">{filters.value.redRange[0]}</span>
          <div class="grow text-xs">
            <SliderPrimitive.Root
              type="multiple"
              min={0}
              max={255}
              step={1}
              value={filters.value.redRange}
              onValueChange={(v) => {
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
          </div>
          <span class="w-8">{filters.value.redRange[1]}</span>
        </div>

        <!-- Green -->
        <div class="flex items-center text-sm text-center text-green-500">
          <span class="text-left w-4">G</span>
          <span class="w-8">{filters.value.greenRange[0]}</span>
          <div class="grow text-xs">
            <SliderPrimitive.Root
              type="multiple"
              min={0}
              max={255}
              step={1}
              value={filters.value.greenRange}
              onValueChange={(v) => {
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
          </div>
          <span class="w-8">{filters.value.greenRange[1]}</span>
        </div>

        <!-- Blue -->
        <div class="flex items-center text-sm text-center text-blue-500">
          <span class="text-left w-4">B</span>
          <span class="w-8">{filters.value.blueRange[0]}</span>
          <div class="grow text-xs">
            <SliderPrimitive.Root
              type="multiple"
              min={0}
              max={255}
              step={1}
              value={filters.value.blueRange}
              onValueChange={(v) => {
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
          </div>
          <span class="w-8">{filters.value.blueRange[1]}</span>
        </div>
      {/if}
    </div>

    <!-- 16-BIT SETTINGS -->
    {#if safeItemFormat === "16bit"}
      <div class="mt-4 border border-border rounded py-2 px-4 text-sm">
        <h4 class="uppercase font-medium h-6 text-muted-foreground">16-BIT SETTINGS</h4>
        <div class="my-1">Select range :</div>
        <div class="flex items-center text-sm text-center">
          <input
            type="number"
            class="w-16 bg-inherit outline-none text-center"
            bind:value={filters.value.u16BitRange[0]}
          />
          <div class="grow text-xs">
            <SliderPrimitive.Root
              type="multiple"
              min={0}
              max={65535}
              step={1}
              value={filters.value.u16BitRange}
              onValueChange={(v) => {
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
          </div>
          <input
            type="number"
            class="w-16 bg-inherit outline-none text-center"
            bind:value={filters.value.u16BitRange[1]}
          />
        </div>
      </div>
    {/if}
  {/if}
</div>

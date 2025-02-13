<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Slider as SliderPrimitive } from "bits-ui";
  import { ZoomIn, ZoomOut } from "lucide-svelte";

  import { cn } from "../../../lib/utils/styleUtils";

  type $$Props = SliderPrimitive.Props;

  let className: $$Props["class"] = undefined;
  export let value: $$Props["value"] = [0];
  export { className as class };
</script>

<div
  class={cn("relative flex justify-between items-center gap-4 p-4 w-full", className)}
  {...$$restProps}
>
  <div title="Zoom out" class="text-primary">
    <ZoomOut />
  </div>
  <SliderPrimitive.Root
    bind:value
    class={cn("relative flex w-full touch-none select-none items-center", className)}
    {...$$restProps}
  >
    <span class="relative h-2 w-full grow overflow-hidden rounded-full bg-secondary">
      <SliderPrimitive.Range class="absolute h-full bg-primary" />
    </span>
    <SliderPrimitive.Thumb
      class="block h-4 w-4 rounded-full border-2 border-primary bg-background ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50"
    />
  </SliderPrimitive.Root>
  <div title="Zoom in" class="text-primary">
    <ZoomIn />
  </div>
</div>

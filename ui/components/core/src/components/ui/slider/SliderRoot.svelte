<script lang="ts">
  import { Slider as SliderPrimitive } from "bits-ui";
  import { cn } from "../../../lib/utils/styleUtils";

  type $$Props = SliderPrimitive.Props;

  let className: $$Props["class"] = undefined;
  export let value: $$Props["value"] = [0];
  export { className as class };

  let isMouseOverThumb: boolean = false;

  $: pourcentage = Math.round(((value?.[0] || 0) / $$restProps.max) * 100);
  $: displayedValue = `${pourcentage / 100}`;
</script>

<div class="flex gap-4">
  <span>0</span>
  <SliderPrimitive.Root
    bind:value
    class={cn(" relative flex w-full touch-none select-none items-center", className)}
    {...$$restProps}
  >
    <span class="relative h-2 w-full grow overflow-hidden rounded-full bg-white">
      <SliderPrimitive.Range class="absolute h-full bg-primary" />
    </span>
    <button
      on:mouseenter={() => (isMouseOverThumb = true)}
      on:mouseleave={() => (isMouseOverThumb = false)}
      role="slider"
      aria-valuemin="0"
      aria-valuemax="100"
      aria-valuenow={pourcentage}
      data-melt-part="thumb"
      tabindex="0"
      data-melt-slider-thumb=""
      class={cn(
        "block h-5 w-5 rounded-full border-2 border-primary bg-background ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
        { "h-10 w-10": isMouseOverThumb },
      )}
      data-bits-slider-thumb=""
      style={`position: absolute; left: ${pourcentage}%; translate: -50%;`}
      >{#if isMouseOverThumb && pourcentage > 0 && pourcentage < $$restProps.max * 100}{displayedValue}
      {/if}</button
    >
  </SliderPrimitive.Root>
  <span>{$$restProps.max}</span>
</div>

<script lang="ts">
  import type { HTMLInputAttributes } from "svelte/elements";
  import { cn } from "../../../utils";
  import type { InputEvents } from ".";

  type $$Props = HTMLInputAttributes;
  type $$Events = InputEvents;

  let className: $$Props["class"] = undefined;
  export let value: $$Props["value"] = undefined;
  export { className as class };
</script>

<div
  class={cn(
    "flex h-10 items-center rounded-md border border-input bg-white pl-3 text-sm ring-offset-background focus-within:ring-1 focus-within:ring-ring focus-within:ring-offset-2",
    className,
  )}
>
  <slot />
  <input
    class={cn(
      "w-full p-2 placeholder:text-muted-foreground focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50",
      className,
    )}
    bind:value
    on:blur
    on:change
    on:click
    on:focus
    on:keydown
    on:keypress
    on:keyup
    on:mouseover
    on:mouseenter
    on:mouseleave
    on:paste
    on:input
    {...$$restProps}
  />
</div>

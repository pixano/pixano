<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import type { HTMLInputAttributes } from "svelte/elements";

  import type { InputEvents } from ".";
  import { cn } from "../../../lib/utils/styleUtils";

  type $$Props = HTMLInputAttributes;
  type $$Events = InputEvents; // eslint-disable-line @typescript-eslint/no-unused-vars

  let className: $$Props["class"] = undefined;
  export let value: $$Props["value"] = undefined;
  export { className as class };
  export let autofocus: $$Props["autofocus"] = false;
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
    {...autofocus ? { autofocus: true } : {}}
  />
</div>

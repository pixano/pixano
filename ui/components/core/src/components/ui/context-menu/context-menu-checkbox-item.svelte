<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { ContextMenu as ContextMenuPrimitive } from "bits-ui";
  import { Check } from "lucide-svelte";

  import { cn } from "../../../lib/utils/styleUtils";

  type $$Props = ContextMenuPrimitive.CheckboxItemProps;
  type $$Events = ContextMenuPrimitive.CheckboxItemEvents; // eslint-disable-line @typescript-eslint/no-unused-vars

  let className: $$Props["class"] = undefined;
  export let checked: $$Props["checked"] = undefined;
  export { className as class };
</script>

<ContextMenuPrimitive.CheckboxItem
  bind:checked
  class={cn(
    "relative flex cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none data-[disabled]:pointer-events-none data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground data-[disabled]:opacity-50",
    className,
  )}
  {...$$restProps}
  on:click
  on:keydown
  on:focusin
  on:focusout
  on:pointerdown
  on:pointerleave
  on:pointermove
>
  <span class="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
    <ContextMenuPrimitive.CheckboxIndicator>
      <Check class="h-4 w-4" />
    </ContextMenuPrimitive.CheckboxIndicator>
  </span>
  <slot />
</ContextMenuPrimitive.CheckboxItem>

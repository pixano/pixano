<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Popover as PopoverPrimitive } from "bits-ui";
  import { cn, flyAndScale } from "../../../lib/utils/styleUtils";

  type $$Props = PopoverPrimitive.ContentProps;
  let className: $$Props["class"] = undefined;
  export let transition: $$Props["transition"] = flyAndScale;
  export let transitionConfig: $$Props["transitionConfig"] = undefined;
  export { className as class };
</script>

<PopoverPrimitive.Content
  {transition}
  {transitionConfig}
  class={cn(
    "z-50 w-72 rounded-md border bg-popover p-4 text-popover-foreground shadow-md outline-none",
    className,
  )}
  {...$$restProps}
>
  <slot />
</PopoverPrimitive.Content>

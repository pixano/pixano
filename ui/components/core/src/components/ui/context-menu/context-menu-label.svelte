<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { ContextMenu as ContextMenuPrimitive } from "bits-ui";

  import { cn } from "../../../lib/utils/styleUtils";

  type $$Props = ContextMenuPrimitive.LabelProps & {
    inset?: boolean;
  };

  let className: $$Props["class"] = undefined;
  export let inset: $$Props["inset"] = undefined;
  export { className as class };
</script>

<ContextMenuPrimitive.Label
  class={cn("px-2 py-1.5 text-sm font-semibold text-foreground", inset && "pl-8", className)}
  {...$$restProps}
>
  <slot />
</ContextMenuPrimitive.Label>

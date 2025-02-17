<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { ContextMenu as ContextMenuPrimitive } from "bits-ui";

  import { cn } from "../../../lib/utils/styleUtils";

  type $$Props = ContextMenuPrimitive.SeparatorProps;

  let className: $$Props["class"] = undefined;
  export { className as class };
</script>

<ContextMenuPrimitive.Separator
  class={cn("-mx-1 my-1 h-px bg-border", className)}
  {...$$restProps}
/>

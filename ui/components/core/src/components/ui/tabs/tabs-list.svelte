<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Tabs as TabsPrimitive } from "bits-ui";

  import { cn } from "../../../lib/utils/styleUtils";

  type $$Props = TabsPrimitive.ListProps;

  let className: $$Props["class"] = undefined;
  export { className as class };
</script>

<TabsPrimitive.List
  class={cn("inline-flex w-full h-10 items-center justify-center text-muted-foreground", className)}
  {...$$restProps}
>
  <slot />
</TabsPrimitive.List>

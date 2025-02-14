<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Command as CommandPrimitive } from "cmdk-sv";

  import { cn } from "../../../lib/utils/styleUtils";

  type $$Props = CommandPrimitive.ListProps;
  let className: string | undefined | null = undefined;
  export { className as class };
</script>

<CommandPrimitive.List
  class={cn("max-h-[300px] overflow-y-auto overflow-x-hidden", className)}
  {...$$restProps}
>
  <slot />
</CommandPrimitive.List>

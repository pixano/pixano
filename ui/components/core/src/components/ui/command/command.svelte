<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Command as CommandPrimitive } from "cmdk-sv";

  import { cn } from "../../../lib/utils/styleUtils";

  type $$Props = CommandPrimitive.CommandProps;

  export let value: $$Props["value"] = undefined;

  let className: string | undefined | null = undefined;
  export { className as class };
</script>

<CommandPrimitive.Root
  class={cn(
    "flex h-full w-full flex-col overflow-hidden rounded-md bg-popover text-popover-foreground relative",
    className,
  )}
  bind:value
  {...$$restProps}
>
  <slot />
</CommandPrimitive.Root>

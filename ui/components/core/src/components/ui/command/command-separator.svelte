<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Command as CommandPrimitive } from "cmdk-sv";
  import { cn } from "../../../lib/utils/styleUtils";

  let className: string | undefined | null = undefined;
  export { className as class };
</script>

<CommandPrimitive.Separator class={cn("-mx-1 h-px bg-border", className)} {...$$restProps} />

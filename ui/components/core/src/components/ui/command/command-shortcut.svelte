<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { cn } from "../../../lib/utils/styleUtils";

  let className: string | undefined | null = undefined;
  export { className as class };
</script>

<span
  class={cn("ml-auto text-xs tracking-widest text-muted-foreground", className)}
  {...$$restProps}
>
  <slot />
</span>

<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import type { HTMLAttributes } from "svelte/elements";

  import { cn } from "../../../lib/utils/styleUtils";

  type $$Props = HTMLAttributes<HTMLSpanElement>;

  let className: $$Props["class"] = undefined;
  export { className as class };
</script>

<span
  class={cn("ml-auto text-xs tracking-widest text-muted-foreground", className)}
  {...$$restProps}
>
  <slot />
</span>

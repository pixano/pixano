<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { HTMLAttributes } from "svelte/elements";

  import { cn } from "../../../lib/utils/styleUtils";

  type $$Props = HTMLAttributes<HTMLParagraphElement>;
  let className: $$Props["class"] = undefined;
  export { className as class };
</script>

<p class={cn("text-sm text-muted-foreground", className)} {...$$restProps}>
  <slot />
</p>

<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { HTMLAttributes } from "svelte/elements";

  import { cn } from "../../../lib/utils/styleUtils";

  type $$Props = HTMLAttributes<HTMLHeadingElement>;
  let className: $$Props["class"] = undefined;
  export { className as class };
</script>

<h3 class={cn("font-semibold leading-none tracking-tight", className)} {...$$restProps}>
  <slot />
</h3>

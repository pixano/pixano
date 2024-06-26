<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { cn } from "../../../lib/utils/styleUtils";
  import type { HTMLAttributes } from "svelte/elements";

  type $$Props = HTMLAttributes<HTMLDivElement>;

  let className: $$Props["class"] = undefined;
  export { className as class };
</script>

<div
  class={cn("flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2", className)}
  {...$$restProps}
>
  <slot />
</div>

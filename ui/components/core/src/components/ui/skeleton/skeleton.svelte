<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import type { HTMLAttributes } from "svelte/elements";

  import { cn } from "../../../lib/utils/styleUtils";

  type $$Props = HTMLAttributes<HTMLDivElement>;

  let className: $$Props["class"] = undefined;
  export { className as class };
</script>

<div class={cn("animate-pulse rounded-md bg-muted/60", className)} {...$$restProps} />

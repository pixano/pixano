<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Dialog as DialogPrimitive } from "bits-ui";
  import { cn } from "../../../lib/utils/styleUtils";

  type $$Props = DialogPrimitive.TitleProps;

  let className: $$Props["class"] = undefined;
  export { className as class };
</script>

<DialogPrimitive.Title
  class={cn("text-lg font-semibold leading-none tracking-tight", className)}
  {...$$restProps}
>
  <slot />
</DialogPrimitive.Title>

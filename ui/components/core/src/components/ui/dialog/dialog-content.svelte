<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Dialog as DialogPrimitive } from "bits-ui";
  import { X } from "lucide-svelte";

  import * as Dialog from ".";
  import { cn, flyAndScale } from "../../../lib/utils/styleUtils";

  type $$Props = DialogPrimitive.ContentProps;

  let className: $$Props["class"] = undefined;
  export let transition: $$Props["transition"] = flyAndScale;
  export let transitionConfig: $$Props["transitionConfig"] = {
    duration: 200,
  };
  export { className as class };
</script>

<Dialog.Portal>
  <Dialog.Overlay />
  <DialogPrimitive.Content
    {transition}
    {transitionConfig}
    class={cn(
      "fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border border-border/40 bg-card/95 backdrop-blur-[24px] p-6 shadow-glass-lg rounded-2xl md:w-full",
      className,
    )}
    {...$$restProps}
  >
    <slot />
    <DialogPrimitive.Close
      class="absolute right-4 top-4 rounded-lg opacity-70 ring-offset-background transition-all duration-150 hover:opacity-100 hover:bg-accent focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground p-1"
    >
      <X class="h-4 w-4" />
      <span class="sr-only">Close</span>
    </DialogPrimitive.Close>
  </DialogPrimitive.Content>
</Dialog.Portal>

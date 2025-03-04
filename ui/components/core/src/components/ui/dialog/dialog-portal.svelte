<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Dialog as DialogPrimitive } from "bits-ui";

  type $$Props = DialogPrimitive.PortalProps; // eslint-disable-line @typescript-eslint/no-unused-vars
</script>

<DialogPrimitive.Portal {...$$restProps}>
  <slot />
</DialogPrimitive.Portal>

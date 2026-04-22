<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import BlockingAlertDialog from "./BlockingAlertDialog.svelte";

  interface Props {
    message: string;
    details?: string;
    moreDetails?: string;
    onConfirm?: () => void;
  }

  let { message, details = "", moreDetails = "", onConfirm }: Props = $props();

  function handleConfirm() {
    onConfirm?.();
  }
</script>

<BlockingAlertDialog
  title={message}
  supportingText={[details, moreDetails]}
  confirmLabel="OK"
  escapeAction="confirm"
  onConfirm={handleConfirm}
/>

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
    confirm?: string;
    alternativeAction?: string;
    onCancel?: () => void;
    onConfirm?: () => void;
    onAlternative?: () => void;
  }

  let {
    message,
    details = "",
    confirm = "Ok",
    alternativeAction = "",
    onCancel,
    onConfirm,
    onAlternative,
  }: Props = $props();

  function handleCancel() {
    onCancel?.();
  }
  function handleConfirm() {
    onConfirm?.();
  }
  function handleAlternativeChoice() {
    onAlternative?.();
  }
</script>

<BlockingAlertDialog
  title={message}
  supportingText={details ? [details] : []}
  confirmLabel={confirm}
  cancelLabel="Cancel"
  alternativeLabel={alternativeAction}
  escapeAction="cancel"
  onCancel={handleCancel}
  onConfirm={handleConfirm}
  onAlternative={handleAlternativeChoice}
/>

<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import BlockingAlertDialog from "./BlockingAlertDialog.svelte";

  interface Props {
    isSaving?: boolean;
    errorMessage?: string | null;
    onCancel?: () => void;
    onDiscard?: () => void;
    onSave?: () => void;
  }

  let { isSaving = false, errorMessage = null, onCancel, onDiscard, onSave }: Props = $props();

  const statusMessage = $derived(isSaving ? "Saving changes..." : (errorMessage ?? ""));
  const statusTone = $derived(isSaving ? "neutral" : "danger");
</script>

<BlockingAlertDialog
  title="Unsaved changes"
  supportingText={["Save changes before leaving this record?"]}
  cancelLabel="Cancel"
  alternativeLabel="Discard"
  confirmLabel="Save"
  escapeAction="cancel"
  cancelDisabled={isSaving}
  alternativeDisabled={isSaving}
  confirmDisabled={isSaving}
  {statusMessage}
  {statusTone}
  isBusy={isSaving}
  {onCancel}
  onAlternative={onDiscard}
  onConfirm={onSave}
/>

<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { connectToInferenceServer } from "$lib/services/inferenceService";
  import { Input, PrimaryButton } from "$lib/ui";

  interface Props {
    defaultUrl?: string;
    onClose?: () => void;
    onConnected?: () => void;
  }

  let { defaultUrl = "", onClose, onConnected }: Props = $props();

  let url = $state("");
  let isConnecting = $state(false);
  let error = $state("");

  $effect(() => {
    url = defaultUrl;
  });

  async function handleConnect() {
    if (!url) return;
    isConnecting = true;
    error = "";
    const success = await connectToInferenceServer(url);
    isConnecting = false;
    if (success) {
      onConnected?.();
      onClose?.();
    } else {
      error = "Could not connect to inference server at this URL.";
    }
  }

  function handleCancel() {
    onClose?.();
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
  onclick={handleCancel}
>
  <div
    onclick={(event) => event.stopPropagation()}
    class="w-96 rounded-xl bg-card text-foreground border border-border shadow-lg"
  >
    <div class="bg-primary p-4 rounded-t-xl text-primary-foreground font-medium">
      Add Inference Server
    </div>
    <div class="p-4 flex flex-col gap-4">
      <div class="flex flex-col gap-1.5">
        <label for="inference-url" class="text-sm font-medium">Server URL</label>
        <Input
          id="inference-url"
          name="inference-url"
          value={url}
          placeholder="http://localhost:8000"
          oninput={(event) => {
            const target = event.currentTarget as HTMLInputElement;
            url = target.value;
          }}
          onkeyup={(e) => {
            e.stopPropagation();
            if (e.key === "Enter") void handleConnect();
          }}
        />
      </div>
      {#if error}
        <p class="text-sm text-destructive">{error}</p>
      {/if}
      <div class="flex gap-3 justify-end">
        <PrimaryButton onclick={handleCancel}>Cancel</PrimaryButton>
        <PrimaryButton onclick={handleConnect} isSelected disabled={!url || isConnecting}>
          {isConnecting ? "Connecting..." : "Connect"}
        </PrimaryButton>
      </div>
    </div>
  </div>
</div>

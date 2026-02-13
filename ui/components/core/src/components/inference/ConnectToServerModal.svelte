<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import { connectToInferenceServer } from "../../lib/services/inferenceService";
  import Input from "../ui/input/input.svelte";
  import PrimaryButton from "../ui/molecules/PrimaryButton.svelte";

  export let defaultUrl = "";

  let url = defaultUrl;
  let isConnecting = false;
  let error = "";

  const dispatch = createEventDispatcher();

  async function handleConnect() {
    if (!url) return;
    isConnecting = true;
    error = "";
    const success = await connectToInferenceServer(url);
    isConnecting = false;
    if (success) {
      dispatch("connected");
      dispatch("close");
    } else {
      error = "Could not connect to inference server at this URL.";
    }
  }

  function handleCancel() {
    dispatch("close");
  }
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
  class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
  on:click={handleCancel}
>
  <div
    on:click|stopPropagation={() => {}}
    class="w-96 rounded-xl bg-card text-foreground border border-border shadow-lg"
  >
    <div class="bg-primary p-4 rounded-t-xl text-primary-foreground font-medium">Add Inference Server</div>
    <div class="p-4 flex flex-col gap-4">
      <div class="flex flex-col gap-1.5">
        <label for="inference-url" class="text-sm font-medium">Server URL</label>
        <Input
          id="inference-url"
          name="inference-url"
          value={url}
          placeholder="http://localhost:8000"
          on:change={(e) => {
            if (e.target && "value" in e.target) url = e.target.value;
          }}
          on:keyup={(e) => {
            e.stopPropagation();
            if (e.key === "Enter") void handleConnect();
          }}
        />
      </div>
      {#if error}
        <p class="text-sm text-destructive">{error}</p>
      {/if}
      <div class="flex gap-3 justify-end">
        <PrimaryButton on:click={handleCancel}>Cancel</PrimaryButton>
        <PrimaryButton on:click={handleConnect} isSelected disabled={!url || isConnecting}>
          {isConnecting ? "Connecting..." : "Connect"}
        </PrimaryButton>
      </div>
    </div>
  </div>
</div>

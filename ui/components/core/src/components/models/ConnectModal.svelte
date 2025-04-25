<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import { api, Input, PrimaryButton, type InputEvents } from "../..";

  export let isConnected = false;
  export let url: string;

  // default values
  let formData = {
    pi_url: url,
  };

  const dispatch = createEventDispatcher();

  async function handleConnect() {
    console.log("handleConnect");
    isConnected = await api.isInferenceApiHealthy(formData.pi_url);
    console.log("handleConnect end", isConnected);
    if (isConnected) {
      dispatch("listModels");
      dispatch("cancelConnect"); //also close modal
    }
  }

  function handleCancel() {
    dispatch("cancelConnect");
  }

  const handleChange = (event: InputEvents["change"]) => {
    if (event.target && "name" in event.target && "value" in event.target) {
      const name: string = event.target.name as string;
      const value: string = event.target.value as string;
      formData = { ...formData, [name]: value };
    }
  };
</script>

<!-- stop propagation to prevent from closing the modal when clicking on the background -->
<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
  on:click|stopPropagation={() => {}}
  class="fixed top-[calc(80px+5px)] left-1/2 transform -translate-x-1/2 z-50 overflow-y-auto w-80 rounded-md bg-white text-slate-800 flex flex-col gap-3"
>
  <div class="bg-primary p-3 rounded-b-none rounded-t-md text-white">
    <p>Pixano Inference connection</p>
  </div>

  <div class="px-3 pb-3 flex flex-col gap-3">
    <h5 class="font-medium">Pixano Inference provider URL</h5>
    <Input
      name="pi_url"
      value={formData.pi_url}
      type="string"
      on:change={handleChange}
      on:keyup={(e) => e.stopPropagation()}
    />

    <p class="italic text-justify text-sm">
      Note that the last active connection will be kept after a failed connect attempt.
    </p>

    <div class="flex flex-row gap-4 justify-center">
      <PrimaryButton on:click={handleCancel}>Cancel</PrimaryButton>
      <PrimaryButton on:click={handleConnect} isSelected disabled={formData.pi_url === ""}>
        Connect
      </PrimaryButton>
    </div>
  </div>
</div>

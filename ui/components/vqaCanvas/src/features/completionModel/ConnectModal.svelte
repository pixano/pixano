<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import { PrimaryButton } from "@pixano/core";
  import type { InputEvents } from "@pixano/core/src/components/ui/input";
  import Input from "@pixano/core/src/components/ui/input/input.svelte";

  import { connect } from "../../utils/connect";

  export let isConnected = false;
  export let defaultURL: string;

  // default values
  let formData = {
    pi_url: defaultURL,
  };

  const dispatch = createEventDispatcher();

  async function handleConnect() {
    const newConnection = await connect(formData.pi_url);
    if (!isConnected && newConnection) isConnected = newConnection;
    if (newConnection) {
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
  class="fixed top-[calc(80px+5px)] left-[calc(300px+5px+315px+5px)] z-50 overflow-y-auto w-68 rounded-md bg-white text-slate-800 flex flex-col gap-3 item-center pb-3 max-h-[calc(100vh-80px-10px)]"
>
  <div class="bg-primary p-3 rounded-b-none rounded-t-md text-white">
    <p>Pixano Inference connection</p>
  </div>
  <div class="p-3 flex flex-col gap-2">
    <span>
      <i>
        Please note that the last active
        <br />
        connection will be used, even
        <br />
        after a failed connect attempt.
      </i>
    </span>
    <h5 class="font-medium">Pixano Inference provider URL</h5>
    <div class="flex items-center justify-between">
      <Input
        name="pi_url"
        value={formData.pi_url}
        type="string"
        on:change={handleChange}
        on:keyup={(e) => e.stopPropagation()}
      />
    </div>
    <div class="flex flex-row gap-2 px-3 justify-center">
      <PrimaryButton on:click={handleConnect} isSelected disabled={formData.pi_url === ""}>
        OK
      </PrimaryButton>
      <PrimaryButton on:click={handleCancel}>Cancel</PrimaryButton>
    </div>
  </div>
</div>

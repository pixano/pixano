<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import * as api from "$lib/api";
  import {
    pixanoInferenceSegmentationURL,
    pixanoInferenceTrackingURL,
  } from "$lib/stores/inferenceStores.svelte";
  import { Input, PrimaryButton, type InputEvents } from "$lib/ui";

  interface Props {
    isConnected?: boolean;
    isVideo?: boolean;
    onCancelConnect?: () => void;
    onListModels?: () => void;
  }

  let {
    isConnected = $bindable(false),
    isVideo = false,
    onCancelConnect,
    onListModels,
  }: Props = $props();

  // default values
  let formData = $state({
    pi_url: "",
  });

  $effect(() => {
    formData = {
      pi_url: isVideo ? pixanoInferenceTrackingURL.value : pixanoInferenceSegmentationURL.value,
    };
  });

  async function handleConnect() {
    isConnected = await api.isInferenceApiHealthy(formData.pi_url);
    if (isConnected) {
      if (isVideo) {
        pixanoInferenceTrackingURL.value = formData.pi_url;
      } else {
        pixanoInferenceSegmentationURL.value = formData.pi_url;
      }
      onListModels?.();
      onCancelConnect?.(); //also close modal
    }
  }

  function handleCancel() {
    onCancelConnect?.();
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
<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  onclick={(event) => event.stopPropagation()}
  class="fixed top-[calc(80px+5px)] left-1/2 transform -translate-x-1/2 z-50 w-96
  rounded-md bg-card text-foreground flex flex-col gap-3 item-center pb-3 max-h-[calc(100vh-80px-10px)]"
>
  <div class="bg-primary p-3 rounded-b-none rounded-t-md text-white">
    <p>Pixano Inference connection - Segmentation</p>
  </div>

  <div class="px-3 pb-3 flex flex-col gap-3">
    <h5 class="font-medium">Pixano Inference provider URL</h5>
    <Input
      name="pi_url"
      value={formData.pi_url}
      type="string"
      onchange={handleChange}
      onkeyup={(e) => e.stopPropagation()}
    />

    <p class="italic text-justify text-sm">
      Note that the last active connection will be used, even after a failed connect attempt.
    </p>

    <div class="flex flex-row gap-4 justify-center">
      <PrimaryButton onclick={handleCancel}>Cancel</PrimaryButton>
      <PrimaryButton onclick={handleConnect} isSelected disabled={formData.pi_url === ""}>
        Connect
      </PrimaryButton>
    </div>
  </div>
</div>

<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import * as api from "$lib/api";
  import { Input, PrimaryButton } from "$lib/ui";

  interface Props {
    isConnected?: boolean;
    url: string;
    vqaSectionWidth: number;
    onCancelConnect?: () => void;
    onListModels?: () => void;
  }

  let {
    isConnected = $bindable(false),
    url,
    vqaSectionWidth,
    onCancelConnect,
    onListModels,
  }: Props = $props();

  // default values
  let formData = $state({
    pi_url: "",
  });

  $effect(() => {
    formData = { pi_url: url };
  });

  async function handleConnect() {
    isConnected = await api.isInferenceApiHealthy(formData.pi_url);
    if (isConnected) {
      onListModels?.();
      onCancelConnect?.(); //also close modal
    }
  }

  function handleCancel() {
    onCancelConnect?.();
  }

  const handleChange = (event: Event & { currentTarget: EventTarget & HTMLInputElement }) => {
    const { name, value } = event.currentTarget;
    formData = { ...formData, [name]: value };
  };
</script>

<!-- stop propagation to prevent from closing the modal when clicking on the background -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  onclick={(event) => event.stopPropagation()}
  class="fixed top-[calc(80px+5px)] z-50 overflow-y-auto w-96 rounded-md bg-card text-foreground flex flex-col gap-3"
  style={`left: calc(${vqaSectionWidth}px + 10px);`}
>
  <div class="bg-primary p-3 rounded-b-none rounded-t-md text-white">
    <p>Pixano Inference connection - Completion</p>
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
    <p class="italic text-justify text-sm">
      Also, Pixano Inference does not support several running models, so to have both Completion and
      Segmentation you should use two different Pixano Inference instances.
    </p>

    <div class="flex flex-row gap-4 justify-center">
      <PrimaryButton onclick={handleCancel}>Cancel</PrimaryButton>
      <PrimaryButton onclick={handleConnect} isSelected disabled={formData.pi_url === ""}>
        Connect
      </PrimaryButton>
    </div>
  </div>
</div>

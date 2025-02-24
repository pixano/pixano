<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { onMount } from "svelte";

  import { api, MultimodalImageNLPTask } from "@pixano/core";

  export let selectedModel: string;
  let models: { id: string; value: string }[] = [];

  onMount(() => {
    api.listModels(MultimodalImageNLPTask.CONDITIONAL_GENERATION).then((model_list) => {
      models = model_list.map((model) => {
        return { id: model.name, value: model.name };
      });
    });
  });
</script>

<div class="px-3 flex flex-col gap-2">
  <!-- For some reason, some tailwind classes don't work on select -->
  <!-- Use style instead -->
  <select
    class="py-3 px-2 border rounded-lg border-gray-200 outline-none text-slate-800"
    style="color: #1e293b; border-color: #e5e7eb;"
    bind:value={selectedModel}
  >
    <option value="" selected disabled>Select a model</option>
    {#each models as { id, value }}
      <option value={id}>{value}</option>
    {/each}
  </select>
</div>

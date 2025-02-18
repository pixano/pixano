<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  export let selectedModel: string;

  // TODO: fetch models from API
  const models = [
    { id: "model1", value: "Model 1" },
    { id: "model2", value: "Model 2" },
    { id: "model3", value: "Model 3" },
  ];
</script>

<div class="p-3 flex flex-col gap-2">
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

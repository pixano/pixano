<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Trash2 } from "lucide-svelte";

  export let index: number;
  export let questionChoices: string[];

  const handleDeleteChoice = () => {
    questionChoices = questionChoices.filter((_, i) => i !== index);
  };
</script>

<div class="flex items-center justify-between">
  <h5 class="font-medium">Answer {index + 1}</h5>
  <button
    class="rounded-full p-[6px] hover:bg-primary-light transition duration-300"
    on:click={handleDeleteChoice}
  >
    <Trash2 size={15} />
  </button>
</div>

<!-- svelte-ignore a11y-autofocus -->
<!-- Not an issue here since the input is only mounted if the user clicks on "Add an answer" button ? -->
<input
  placeholder="Type here..."
  autofocus
  type="text"
  class="p-2 border rounded-lg border-gray-200 outline-none text-slate-800 focus:border-primary"
  bind:value={questionChoices[index]}
/>

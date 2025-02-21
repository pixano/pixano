<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Plus } from "lucide-svelte";

  import PrimaryButton from "@pixano/core/src/components/ui/molecules/PrimaryButton.svelte";

  export let questionChoices: string[];

  const handleAddChoice = () => {
    questionChoices = [...questionChoices, ""];
  };
</script>

<PrimaryButton on:click={handleAddChoice}>
  <Plus />
  <p class="text-slate-800">Add an answer</p>
</PrimaryButton>

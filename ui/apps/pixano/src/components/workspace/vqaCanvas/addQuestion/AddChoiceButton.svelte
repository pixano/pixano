<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Plus } from "phosphor-svelte";

  import { PrimaryButton } from "$lib/ui";

  interface Props {
    questionChoices: string[];
  }

  let { questionChoices = $bindable() }: Props = $props();

  const handleAddChoice = () => {
    questionChoices = [...questionChoices, ""];
  };
</script>

<PrimaryButton onclick={handleAddChoice}>
  <Plus />
  <p class="text-foreground">Add an answer</p>
</PrimaryButton>

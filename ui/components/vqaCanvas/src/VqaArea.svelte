<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Settings } from "lucide-svelte";

  import { IconButton, Message } from "@pixano/core";

  import { AddQuestionButton } from "./features/addQuestion/components";
  import { QuestionForm } from "./features/annotateItem/components";
  import { ModelSelectAdd } from "./features/manageModels/components";
  import ConfigurePromptModal from "./features/manageModels/components/ConfigurePromptModal.svelte";
  import { groupMessagesByNumber } from "./utils";

  export let messages: Message[];
  export let vqaSectionWidth: number;

  let showPromptModal = false;

  $: messagesByNumber = groupMessagesByNumber(messages);

  const handleOpenPromptModal = (event: MouseEvent) => {
    // stopPropgation is not called as event modifier
    // because event modifiers can only be used on DOM elements
    event.stopPropagation();
    if (showPromptModal) {
      handleClosePromptModal();
    } else {
      showPromptModal = true;
      document.body.addEventListener("click", handleClosePromptModal);
    }
  };

  const handleClosePromptModal = () => {
    showPromptModal = false;
    document.body.removeEventListener("click", handleClosePromptModal);
  };
</script>

<div class="bg-white p-4 flex flex-col gap-4 h-full overflow-y-auto">
  <ModelSelectAdd {vqaSectionWidth} />

  <div class="flex flex-row gap-2 justify-between">
    <AddQuestionButton {vqaSectionWidth} on:storeQuestion />
    <IconButton
      tooltipContent="Configure generation prompts and tags"
      on:click={handleOpenPromptModal}
    >
      <Settings />
    </IconButton>
  </div>

  {#each messagesByNumber as messages}
    <QuestionForm bind:messages on:answerContentChange on:generateAnswer />
  {/each}
</div>

{#if showPromptModal}
  <ConfigurePromptModal {vqaSectionWidth} on:cancelPrompt={handleClosePromptModal} />
{/if}

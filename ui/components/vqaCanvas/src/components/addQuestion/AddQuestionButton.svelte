<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { PrimaryButton } from "@pixano/core";

  import AddQuestionModal from "./AddQuestionModal.svelte";

  let showAddQuestionModal = false;

  const handleOpenModal = (event: MouseEvent) => {
    // stopPropgation is not called as event modifier
    // because event modifiers can only be used on DOM elements
    event.stopPropagation();
    showAddQuestionModal = true;
    document.body.addEventListener("click", handleCloseModal);
  };

  const handleCloseModal = () => {
    showAddQuestionModal = false;
    document.body.removeEventListener("click", handleCloseModal);
  };

  const handleKeyDown = (
    event: KeyboardEvent & {
      currentTarget: EventTarget & Window;
    },
  ) => {
    if (event.key === "Escape") {
      showAddQuestionModal = false;
    }
  };
</script>

<div class="relative h-fit">
  <PrimaryButton on:click={handleOpenModal}>Add question</PrimaryButton>

  {#if showAddQuestionModal}
    <AddQuestionModal />
  {/if}
</div>

<svelte:window on:keydown={handleKeyDown} />

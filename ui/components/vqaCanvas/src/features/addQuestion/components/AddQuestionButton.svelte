<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import { PrimaryButton } from "@pixano/core";

  import type { StoreQuestionEvent } from "../types";
  import AddQuestionModal from "./AddQuestionModal.svelte";

  export let completionModel: string;

  let showAddQuestionModal = false;

  const dispatch = createEventDispatcher();

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

  const handleStoreQuestion = (event: CustomEvent<StoreQuestionEvent>) => {
    showAddQuestionModal = false;
    dispatch("storeQuestion", event.detail);
  };
</script>

<div class="relative h-fit">
  <PrimaryButton on:click={handleOpenModal}>Add question</PrimaryButton>
  {#if showAddQuestionModal}
    <AddQuestionModal bind:completionModel on:storeQuestion={handleStoreQuestion} />
  {/if}
</div>

<svelte:window on:keydown={handleKeyDown} />

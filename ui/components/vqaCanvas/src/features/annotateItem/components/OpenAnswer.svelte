<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import { AutoResizeTextarea, type Message } from "@pixano/core";
  import { ContentChangeEventType, type ContentChangeEvent } from "../types";

  export let answer: Message | null;
  export let questionId: string;
  export let disabled = false;

  const answerId = answer?.id ?? null;
  let answerContent = answer?.data.content ?? "";
  const dispatch = createEventDispatcher();

  const validateChange = () => {
    const eventDetail: ContentChangeEvent = answerId
      ? { content: answerContent, type: ContentChangeEventType.UPDATE, answerId }
      : { content: answerContent, type: ContentChangeEventType.NEW_ANSWER, questionId };

    dispatch("answerContentChange", eventDetail);
  };
</script>

<AutoResizeTextarea
  placeholder="Type the answer here..."
  bind:value={answerContent}
  on:blur={validateChange}
  {disabled}
  class="w-full bg-transparent border-none focus:ring-0 p-0 text-sm text-slate-700 leading-relaxed placeholder:text-slate-300 {disabled ? 'cursor-default' : ''}"
/>

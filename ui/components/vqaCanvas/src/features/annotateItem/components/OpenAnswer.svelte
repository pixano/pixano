<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { createEventDispatcher, tick } from "svelte";

  import type { Message } from "@pixano/core";

  import { ContentChangeEventType, type ContentChangeEvent } from "../types";

  export let answer: Message | null;
  export let questionId: string;

  const answerId = answer?.id ?? null;
  let answerContent = answer?.data.content ?? "";
  const dispatch = createEventDispatcher();

  let textareaRef: HTMLTextAreaElement | null = null;

  $: if (answerContent) void adjustHeight();

  const validateChange = () => {
    console.log("validateChange");
    const eventDetail: ContentChangeEvent = answerId
      ? { content: answerContent, type: ContentChangeEventType.UPDATE, answerId }
      : { content: answerContent, type: ContentChangeEventType.NEW_ANSWER, questionId };

    dispatch("answerContentChange", eventDetail);
  };

  const adjustHeight = async () => {
    await tick(); //need to await tick to have textareaRef when generated
    if (textareaRef) {
      textareaRef.style.height = "auto";
      await tick(); //need to await tick to have a correct value in textareaRef.scrollHeight
      textareaRef.style.height = textareaRef.scrollHeight + "px";
    }
  };
</script>

<textarea
  placeholder="Your answer here"
  class="p-2 border rounded-lg border-slate-200 outline-none text-slate-800 placeholder-slate-500 focus:border-primary resize-none overflow-hidden"
  bind:this={textareaRef}
  bind:value={answerContent}
  on:blur={validateChange}
/>

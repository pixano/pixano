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
  placeholder="Your answer here"
  bind:value={answerContent}
  on:blur={validateChange}
/>

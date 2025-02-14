<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import { ContentChangeEventType, type ContentChangeEvent } from "../lib/types";
  import type { Message } from "@pixano/core";

  export let answer: Message | null;
  export let questionId: string;

  const answerId = answer?.id ?? null;

  const dispatch = createEventDispatcher();

  const handleBlur = (
    e: FocusEvent & {
      currentTarget: EventTarget & HTMLInputElement;
    },
  ) => {
    const eventDetail: ContentChangeEvent = answerId
      ? { content: e.currentTarget.value, type: ContentChangeEventType.UPDATE, answerId }
      : { content: e.currentTarget.value, type: ContentChangeEventType.NEW_ANSWER, questionId };

    dispatch("answerContentChange", eventDetail);
  };
</script>

<input
  type="text"
  value={answer?.data.content ?? ""}
  placeholder="Your answer here"
  class="p-2 text-slate-800 placeholder-slate-500 outline-none border border-slate-100 rounded-lg"
  on:blur={handleBlur}
/>

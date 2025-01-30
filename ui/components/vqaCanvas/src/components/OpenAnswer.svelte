<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { Message } from "@pixano/core";
  import { createEventDispatcher } from "svelte";

  export let answer: Message;

  const answerId = answer.id;

  const dispatch = createEventDispatcher();

  const handleBlur = (
    e: FocusEvent & {
      currentTarget: EventTarget & HTMLInputElement;
    },
  ) => {
    const newContent = e.currentTarget.value;
    dispatch("answerContentChange", { answerId, newContent });
  };
</script>

<input
  type="text"
  value={answer.data.content}
  placeholder="Your answer here"
  class="p-2 text-slate-800 placeholder-slate-500 outline-none border border-slate-100 rounded-lg"
  on:blur={handleBlur}
/>

<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { Message } from "@pixano/core";
  import { createEventDispatcher } from "svelte";

  export let message: Message;

  const messageId = message.id;

  const dispatch = createEventDispatcher();

  const handleBlur = (
    e: FocusEvent & {
      currentTarget: EventTarget & HTMLInputElement;
    },
  ) => {
    const newMessageContent = e.currentTarget.value;
    dispatch("messageContentChange", { messageId, newMessageContent });
  };
</script>

<input
  type="text"
  value={message.data.content}
  placeholder="Your answer here"
  class="p-2 text-slate-800 placeholder-slate-500 bg-slate-50 outline-none"
  on:blur={handleBlur}
/>

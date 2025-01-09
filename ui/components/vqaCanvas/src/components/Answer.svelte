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
      currentTarget: EventTarget & HTMLDivElement;
    },
  ) => {
    const editableDiv = e.currentTarget;
    const newMessageContent = editableDiv.innerText;

    dispatch("messageContentChange", { messageId, newMessageContent });
  };
</script>

<div
  on:blur={handleBlur}
  contenteditable="true"
  class="outline-none flex flex-row flex-wrap items-center"
  role="textbox"
  tabindex="0"
>
  {message.data.content}
</div>

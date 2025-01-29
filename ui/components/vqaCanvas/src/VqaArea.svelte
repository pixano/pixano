<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Message } from "@pixano/core";
  import { QuestionForm } from "./components";
  import { groupMessagesByNumber } from "./utils";

  // Exports
  export let messages: Message[];

  const messagesByNumber = groupMessagesByNumber(messages);
</script>

<div class="bg-white p-4 flex flex-col gap-4 h-full overflow-y-auto">
  {#each messagesByNumber as messages}
    <QuestionForm {messages} />
  {/each}
</div>

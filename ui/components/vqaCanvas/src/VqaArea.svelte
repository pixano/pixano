<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">

  import { Message, MessageTypeEnum } from "@pixano/core";

  import { groupMessagesByNumber } from "./utils";

  import VqaHeader from "./features/annotateItem/components/VqaHeader.svelte";

  import VqaChatThread from "./features/annotateItem/components/VqaChatThread.svelte";

  import VqaInputArea from "./features/annotateItem/components/VqaInputArea.svelte";

  import { isQuestionCompleted } from "./features/annotateItem/utils";



  export let messages: Message[];

  export let vqaSectionWidth: number;



  $: messagesByNumber = groupMessagesByNumber(messages);

  

  // Find the last question group and check if it has an answer

  $: lastGroup = messagesByNumber.length > 0 ? messagesByNumber[messagesByNumber.length - 1] : null;

  $: pendingQuestion = lastGroup && !isQuestionCompleted(lastGroup) ? 

      lastGroup.find(m => m.data.type === MessageTypeEnum.QUESTION) : null;

</script>



<div class="flex flex-col h-full bg-slate-50 overflow-hidden">

  <VqaHeader {vqaSectionWidth} />



  <div class="flex-1 overflow-hidden">

    <VqaChatThread

      {messagesByNumber}

      on:answerContentChange

      on:generateAnswer

      on:deleteQuestion

    />

  </div>



        <VqaInputArea 



          {pendingQuestion}



          on:storeQuestion 



          on:answerContentChange



          on:generateAnswer



        />



    



  

</div>





<style>

</style>

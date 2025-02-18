<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { QuestionTypeEnum, RadioGroup } from "@pixano/core";

  export let questionType: QuestionTypeEnum;

  const availableQuestionTypes: { id: QuestionTypeEnum; value: string }[] = [
    { id: QuestionTypeEnum.OPEN, value: "Question ouverte" },
    { id: QuestionTypeEnum.SINGLE_CHOICE, value: "Choix unique sans justification" },
    { id: QuestionTypeEnum.SINGLE_CHOICE_EXPLANATION, value: "Choix unique avec justification" },
    { id: QuestionTypeEnum.MULTI_CHOICE, value: "Choix multiple sans justification" },
    { id: QuestionTypeEnum.MULTI_CHOICE_EXPLANATION, value: "Choix multiple avec justification" },
  ];
</script>

<div class="p-3 flex flex-col gap-2">
  <h5 class="font-medium">Type de question</h5>
  <RadioGroup
    bind:selectedValue={questionType}
    values={availableQuestionTypes}
    itemClass="text-slate-800 text-base font-normal"
  />
</div>

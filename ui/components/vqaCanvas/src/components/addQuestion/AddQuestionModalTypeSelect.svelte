<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { QuestionTypeEnum, RadioGroup } from "@pixano/core";

  export let questionType: QuestionTypeEnum;

  const availableQuestionTypes: { id: QuestionTypeEnum; value: string }[] = [
    { id: QuestionTypeEnum.OPEN, value: "Open" },
    { id: QuestionTypeEnum.SINGLE_CHOICE, value: "Single choice without explanation" },
    { id: QuestionTypeEnum.SINGLE_CHOICE_EXPLANATION, value: "Single choice with explanation" },
    { id: QuestionTypeEnum.MULTI_CHOICE, value: "Multiple choice without explanation" },
    { id: QuestionTypeEnum.MULTI_CHOICE_EXPLANATION, value: "Multiple choice with explanation" },
  ];
</script>

<div class="p-3 flex flex-col gap-2">
  <h5 class="font-medium">Question type</h5>
  <RadioGroup
    bind:selectedValue={questionType}
    values={availableQuestionTypes}
    itemClass="text-slate-800 text-base font-normal"
  />
</div>

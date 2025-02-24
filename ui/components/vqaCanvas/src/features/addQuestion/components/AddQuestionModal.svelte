<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Sparkles } from "lucide-svelte";

  import {
    api,
    BaseSchema,
    Conversation,
    Message,
    QuestionTypeEnum,
    type CondititionalGenerationTextImageInput,
  } from "@pixano/core";
  import PrimaryButton from "@pixano/core/src/components/ui/molecules/PrimaryButton.svelte";

  import { currentDatasetStore } from "../../../../../../apps/pixano/src/lib/stores/datasetStores";
  import {
    entities,
    itemMetas,
  } from "../../../../../datasetItemWorkspace/src/lib/stores/datasetItemWorkspaceStores";
  import { default as ModelSelect } from "./AddQuestionModalModelSelect.svelte";
  import { default as QuestionTypeSelect } from "./AddQuestionModalTypeSelect.svelte";
  import NewQuestionForm from "./NewQuestionForm.svelte";

  let questionType: QuestionTypeEnum;
  let completionModel: string;
  let questionChoices: string[] = [];
  let questionContent: string = "";

  const handleGenerateQuestion = () => {
    //TEST TMP: get dataset item metadata for a more dedicated question
    const all_feats = $itemMetas.item.data;
    const { split, ...feats } = all_feats;

    let conv_ui: Conversation = $entities.filter((e) =>
      e.is_type(BaseSchema.Conversation),
    )[0] as Conversation;

    //TMP WIP -- this is to get the Conversation messages (childs)
    //But here we want to generate a QUESTION ! So we will provide a fake Message, that ask for a question...
    // let msgs: Message[] = [];
    // if (conv_ui.ui.childs) {
    //   for (const ann of conv_ui.ui.childs) {
    //     if (ann.is_type(BaseSchema.Message)) {
    //       const { ui, ...no_ui_ann } = ann;
    //       msgs.push(no_ui_ann as Message);
    //     }
    //   }
    // }

    //Prompt as fake Message to get a QUESTION --for convenience, we clone the first message and change the content
    let prompt: Message | null = null;
    const tmp_prompt = conv_ui.ui.childs?.filter((ann) => ann.is_type(BaseSchema.Message));
    if (tmp_prompt && tmp_prompt.length > 0) {
      const { ui, ...no_ui_ann } = tmp_prompt[0]; // eslint-disable-line @typescript-eslint/no-unused-vars
      prompt = structuredClone(no_ui_ann) as Message;
      prompt.data.content =
        "You have to formulate a QUESTION in relation to the given image <image 1>." +
        `If you find it helpfull, you can get inspiration from the following metadata (as a JSON dict): ${JSON.stringify(feats)}` +
        "Please also provide the expected answer.";
      prompt.data.question_type = QuestionTypeEnum.OPEN;
      prompt.data.choices = [];
      //prompt.data.content = `Please formulate a relevant question about the <image 1>`;
    }
    if (!prompt) return;

    console.log("Prompt:", prompt?.data.content);

    //requires to strip ui to avoir circular ref
    const { ui, ...conv } = conv_ui; // eslint-disable-line @typescript-eslint/no-unused-vars

    const input: CondititionalGenerationTextImageInput = {
      dataset_id: $currentDatasetStore.id,
      conversation: conv as Conversation,
      messages: [prompt],
      model: "llava-qwen",
    };
    console.log("Model Input:", input);
    api
      .conditional_generation_text_image(input)
      .then((ann) => {
        console.log("Model output: ", ann);
        console.log(`Model answer: ${(ann as Message).data.content}`);
        console.log(`Model answer string length: ${(ann as Message).data.content.length}`);
        questionContent = (ann as Message).data.content;
        questionChoices = [];
      })
      .catch((err) => {
        console.error("Model genration error:", err);
      });
  };
</script>

<!-- stop propagation to prevent from closing the modal when clicking on the background -->
<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
  on:click|stopPropagation={() => {}}
  class="fixed top-[calc(80px+5px)] left-[calc(300px+5px)] z-50 overflow-y-auto w-68 rounded-md bg-white text-slate-800 flex flex-col gap-3 item-center pb-3 max-h-[calc(100vh-80px-10px)]"
>
  <div class="bg-primary p-3 rounded-b-none rounded-t-md text-white">
    <p>QA editor</p>
  </div>

  <QuestionTypeSelect bind:questionType />
  <ModelSelect bind:selectedModel={completionModel} />

  <div class="flex flex-col gap-2 px-3">
    <PrimaryButton
      isSelected
      disabled={questionType === undefined || completionModel === ""}
      on:click={handleGenerateQuestion}
    >
      <Sparkles size={20} />Generate
    </PrimaryButton>
  </div>

  {#if questionType !== undefined}
    <NewQuestionForm {questionType} bind:questionChoices bind:questionContent on:storeQuestion />
  {/if}
</div>

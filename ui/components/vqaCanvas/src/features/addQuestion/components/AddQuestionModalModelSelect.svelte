<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { onMount } from "svelte";

  import { api, MultimodalImageNLPTask, type ModelConfig } from "@pixano/core";

  export let selectedModel: string;
  let models: { id: string; value: string }[] = [];

  onMount(() => {
    const inference_url = "http://localhost:9152";
    api
      .inferenceConnect(inference_url)
      .then(() => {
        console.log("connected to Pixano Inference at:", inference_url);
        //instanciate a model
        const model_config: ModelConfig = {
          config: {
            name: "llava-qwen",
            task: "image_text_conditional_generation",
            path: "llava-hf/llava-onevision-qwen2-0.5b-ov-hf",
            config: { dtype: "bfloat16" },
            processor_config: {},
          },
          provider: "vllm",
        };
        api
          .listModels(MultimodalImageNLPTask.CONDITIONAL_GENERATION)
          .then((previous_models) => {
            const has_qwen =
              previous_models.filter((m) => m.name === model_config.config.name).length === 1;
            if (has_qwen) {
              models = previous_models.map((model) => {
                return { id: model.name, value: model.name };
              });
            } else {
              api
                .instantiateModel(model_config) //NOTE: take some time (~40sec)
                .then(() => {
                  console.log(`Model '${model_config.config.name}' added.`);
                  //listModels
                  api
                    .listModels(MultimodalImageNLPTask.CONDITIONAL_GENERATION)
                    .then((new_models) => {
                      models = new_models.map((model) => {
                        return { id: model.name, value: model.name };
                      });
                    })
                    .catch((err) => console.error("Can't list models", err));
                })
                .catch((err) =>
                  console.error(`Couldn't instantiate model '${model_config.config.name}'`, err),
                );
            }
          })
          .catch((err) => console.error("Can't list models", err));
      })
      .catch(() => {
        console.error("NOT connected to Pixano Inference!");
      });
  });
</script>

<div class="px-3 flex flex-col gap-2">
  <!-- For some reason, some tailwind classes don't work on select -->
  <!-- Use style instead -->
  <select
    class="py-3 px-2 border rounded-lg border-gray-200 outline-none text-slate-800"
    style="color: #1e293b; border-color: #e5e7eb;"
    bind:value={selectedModel}
  >
    <option value="" selected disabled>Select a model</option>
    {#each models as { id, value }}
      <option value={id}>{value}</option>
    {/each}
  </select>
</div>

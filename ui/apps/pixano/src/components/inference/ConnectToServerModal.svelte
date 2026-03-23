<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Select } from "bits-ui";
  import { CaretUpDown, Check } from "phosphor-svelte";

  import { connectToInferenceServer } from "$lib/services/inferenceService";
  import { Input, PrimaryButton } from "$lib/ui";

  interface Props {
    defaultUrl?: string;
    onClose?: () => void;
    onConnected?: () => void;
  }

  let { defaultUrl = "", onClose, onConnected }: Props = $props();

  const providerTypes = [
    { value: "pixano-inference", label: "Pixano Inference", urlRequired: true, apiKeyRequired: false, defaultUrl: "" },
    { value: "openai", label: "OpenAI", urlRequired: false, apiKeyRequired: true, defaultUrl: "https://api.openai.com" },
    { value: "gemini", label: "Gemini", urlRequired: false, apiKeyRequired: true, defaultUrl: "https://generativelanguage.googleapis.com" },
    { value: "vllm", label: "vLLM", urlRequired: true, apiKeyRequired: false, defaultUrl: "" },
    { value: "lmstudio", label: "LM Studio", urlRequired: true, apiKeyRequired: false, defaultUrl: "" },
    { value: "ollama", label: "Ollama", urlRequired: true, apiKeyRequired: false, defaultUrl: "http://localhost:11434" },
  ];

  const providerItems = providerTypes.map((p) => ({ value: p.value, label: p.label }));

  let selectedType = $state("pixano-inference");
  let url = $state("");
  let apiKey = $state("");
  let isConnecting = $state(false);
  let error = $state("");

  let selectedProvider = $derived(providerTypes.find((p) => p.value === selectedType)!);
  let selectedLabel = $derived(selectedProvider.label);
  let showUrl = $derived(selectedProvider.urlRequired || selectedProvider.defaultUrl !== "");
  let showApiKey = $derived(selectedProvider.apiKeyRequired || ["vllm", "lmstudio", "ollama"].includes(selectedType));

  $effect(() => {
    url = defaultUrl || selectedProvider.defaultUrl;
  });

  let canConnect = $derived.by(() => {
    if (isConnecting) return false;
    if (selectedProvider.urlRequired && !url.trim()) return false;
    if (selectedProvider.apiKeyRequired && !apiKey.trim()) return false;
    return true;
  });

  function handleTypeChange(value: string) {
    selectedType = value;
    apiKey = "";
    error = "";
  }

  async function handleConnect() {
    if (!canConnect) return;

    isConnecting = true;
    error = "";

    const finalUrl = url.trim() || null;
    const finalApiKey = apiKey.trim() || null;

    const result = await connectToInferenceServer(finalUrl, selectedType, finalApiKey);
    isConnecting = false;

    if (result.success) {
      onConnected?.();
      onClose?.();
    } else {
      error = (result as { success: false; error: string }).error;
    }
  }

  function handleCancel() {
    onClose?.();
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
  onclick={handleCancel}
>
  <div
    onclick={(event) => event.stopPropagation()}
    class="w-96 rounded-xl bg-card text-foreground border border-border shadow-lg"
  >
    <div class="bg-primary p-4 rounded-t-xl text-primary-foreground font-medium">
      Add Inference Provider
    </div>
    <div class="p-4 flex flex-col gap-4">
      <div class="flex flex-col gap-1.5">
        <label for="provider-type" class="text-sm font-medium">Provider Type</label>
        <Select.Root
          type="single"
          value={selectedType}
          onValueChange={handleTypeChange}
          items={providerItems}
        >
          <Select.Trigger
            class="justify-between h-10 px-4 py-2 border border-input rounded-md bg-background text-sm inline-flex items-center w-full"
          >
            {selectedLabel}
            <CaretUpDown weight="regular" class="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </Select.Trigger>
          <Select.Portal>
            <Select.Content
              class="z-50 rounded-md border bg-popover p-1 text-popover-foreground shadow-md"
            >
              {#each providerItems as item (item.value)}
                <Select.Item
                  value={item.value}
                  label={item.label}
                  class="flex items-center gap-2 rounded-sm px-2 py-1.5 text-sm cursor-pointer data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground"
                >
                  <Check class="h-4 w-4 {selectedType !== item.value ? 'text-transparent' : ''}" />
                  {item.label}
                </Select.Item>
              {/each}
            </Select.Content>
          </Select.Portal>
        </Select.Root>
      </div>

      {#if showUrl}
        <div class="flex flex-col gap-1.5">
          <label for="inference-url" class="text-sm font-medium">
            Server URL{#if !selectedProvider.urlRequired} (optional){/if}
          </label>
          <Input
            id="inference-url"
            name="inference-url"
            value={url}
            placeholder={selectedProvider.defaultUrl || "http://localhost:8000"}
            oninput={(event) => {
              const target = event.currentTarget as HTMLInputElement;
              url = target.value;
            }}
            onkeyup={(event: KeyboardEvent) => {
              event.stopPropagation();
              if (event.key === "Enter") void handleConnect();
            }}
          />
        </div>
      {/if}

      {#if showApiKey}
        <div class="flex flex-col gap-1.5">
          <label for="inference-api-key" class="text-sm font-medium">
            API Key{#if !selectedProvider.apiKeyRequired} (optional){/if}
          </label>
          <Input
            id="inference-api-key"
            name="inference-api-key"
            type="password"
            value={apiKey}
            placeholder="Enter API key"
            oninput={(event) => {
              const target = event.currentTarget as HTMLInputElement;
              apiKey = target.value;
            }}
            onkeyup={(event: KeyboardEvent) => {
              event.stopPropagation();
              if (event.key === "Enter") void handleConnect();
            }}
          />
        </div>
      {/if}

      {#if error}
        <p class="text-sm text-destructive">{error}</p>
      {/if}
      <div class="flex gap-3 justify-end">
        <PrimaryButton onclick={handleCancel}>Cancel</PrimaryButton>
        <PrimaryButton onclick={handleConnect} isSelected disabled={!canConnect}>
          {isConnecting ? "Connecting..." : "Connect"}
        </PrimaryButton>
      </div>
    </div>
  </div>
</div>

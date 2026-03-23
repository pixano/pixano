<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Select } from "bits-ui";
  import { CaretDown, Check, WarningCircle, X } from "phosphor-svelte";

  import { connectToInferenceServer } from "$lib/services/inferenceService";
  import { AiProcessingBadge, cn } from "$lib/ui";

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
    { value: "litellm", label: "LiteLLM", urlRequired: false, apiKeyRequired: false, defaultUrl: "http://localhost:4000" },
  ];

  const providerItems = providerTypes.map((p) => ({ value: p.value, label: p.label }));

  let selectedType = $state("pixano-inference");
  let url = $state("");
  let apiKey = $state("");
  let isConnecting = $state(false);
  let error = $state("");
  let isProviderOpen = $state(false);

  let selectedProvider = $derived(providerTypes.find((p) => p.value === selectedType)!);
  let selectedLabel = $derived(selectedProvider.label);
  let showUrl = $derived(selectedProvider.urlRequired || selectedProvider.defaultUrl !== "");
  let showApiKey = $derived(selectedProvider.apiKeyRequired || ["vllm", "lmstudio", "ollama", "litellm"].includes(selectedType));

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

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === "Escape") onClose?.();
  }
</script>

<svelte:window onkeydown={handleKeyDown} />

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
  onclick={onClose}
>
  <div
    onclick={(event) => event.stopPropagation()}
    class="w-[26rem] rounded-2xl bg-card text-foreground border border-border/50 shadow-2xl"
  >
    <!-- Header -->
    <div class="flex items-center justify-between px-6 pt-6 pb-4">
      <h2 class="text-base font-semibold text-foreground">Add Inference Provider</h2>
      <button
        type="button"
        onclick={onClose}
        class="h-7 w-7 flex items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
      >
        <X weight="regular" size={16} />
      </button>
    </div>

    <!-- Content -->
    <div class="px-6 pb-6 flex flex-col gap-4">
      <!-- Provider type -->
      <div class="flex flex-col gap-2">
        <span class="text-[13px] font-medium text-muted-foreground">Provider</span>
        <Select.Root
          type="single"
          value={selectedType}
          onValueChange={handleTypeChange}
          items={providerItems}
          open={isProviderOpen}
          onOpenChange={(open) => (isProviderOpen = open)}
        >
          <Select.Trigger
            class={cn(
              "justify-between h-10 px-3.5 py-2 rounded-xl border text-sm inline-flex items-center w-full transition-all duration-150",
              "bg-background text-foreground border-border",
              "hover:border-border/80 hover:bg-muted/30",
              { "border-primary/50 ring-4 ring-primary/5": isProviderOpen },
            )}
          >
            <span class="font-medium">{selectedLabel}</span>
            <CaretDown
              class={cn(
                "h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200",
                { "rotate-180": isProviderOpen },
              )}
            />
          </Select.Trigger>
          <Select.Portal>
            <Select.Content
              sideOffset={6}
              class="z-50 w-[--bits-select-trigger-width] overflow-hidden rounded-xl border border-border/50 bg-popover p-1 text-popover-foreground shadow-[0_12px_36px_rgba(0,0,0,0.15)] backdrop-blur-md"
            >
              {#each providerItems as item (item.value)}
                {@const isSelected = selectedType === item.value}
                <Select.Item
                  value={item.value}
                  label={item.label}
                  class="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm cursor-pointer outline-none transition-colors data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground"
                >
                  <div
                    class={cn(
                      "flex h-5 w-5 shrink-0 items-center justify-center rounded-md border",
                      isSelected
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border/50 text-transparent",
                    )}
                  >
                    <Check class="h-3 w-3" />
                  </div>
                  <span class={cn("font-medium", { "text-foreground": isSelected })}>{item.label}</span>
                </Select.Item>
              {/each}
            </Select.Content>
          </Select.Portal>
        </Select.Root>
      </div>

      <!-- Server URL -->
      {#if showUrl}
        <div class="flex flex-col gap-2">
          <span class="text-[13px] font-medium text-muted-foreground">
            Server URL{#if !selectedProvider.urlRequired}
              <span class="font-normal opacity-60">(optional)</span>
            {/if}
          </span>
          <input
            type="text"
            value={url}
            placeholder={selectedProvider.defaultUrl || "http://localhost:8000"}
            oninput={(event) => {
              url = (event.currentTarget as HTMLInputElement).value;
            }}
            onkeyup={(event) => {
              event.stopPropagation();
              if ((event as KeyboardEvent).key === "Enter") void handleConnect();
            }}
            class="h-10 px-3.5 rounded-xl border border-border bg-background text-sm text-foreground placeholder:text-muted-foreground outline-none transition-all focus:border-primary/50 focus:ring-4 focus:ring-primary/5"
          />
        </div>
      {/if}

      <!-- API Key -->
      {#if showApiKey}
        <div class="flex flex-col gap-2">
          <span class="text-[13px] font-medium text-muted-foreground">
            API Key{#if !selectedProvider.apiKeyRequired}
              <span class="font-normal opacity-60">(optional)</span>
            {/if}
          </span>
          <input
            type="password"
            value={apiKey}
            placeholder="Enter API key"
            oninput={(event) => {
              apiKey = (event.currentTarget as HTMLInputElement).value;
            }}
            onkeyup={(event) => {
              event.stopPropagation();
              if ((event as KeyboardEvent).key === "Enter") void handleConnect();
            }}
            class="h-10 px-3.5 rounded-xl border border-border bg-background text-sm text-foreground placeholder:text-muted-foreground outline-none transition-all focus:border-primary/50 focus:ring-4 focus:ring-primary/5"
          />
        </div>
      {/if}

      <!-- Error -->
      {#if error}
        <div
          class="flex items-start gap-2.5 rounded-xl border border-destructive/30 bg-destructive/5 px-3.5 py-2.5 text-sm text-destructive"
        >
          <WarningCircle weight="regular" class="h-4 w-4 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      {/if}

      <!-- Actions -->
      <div class="flex gap-3 justify-end pt-1">
        <button
          type="button"
          onclick={onClose}
          class="px-4 py-2 rounded-xl text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        >
          Cancel
        </button>
        <button
          type="button"
          onclick={() => void handleConnect()}
          disabled={!canConnect}
          class="px-5 py-2 rounded-xl bg-primary text-primary-foreground text-sm font-medium shadow-sm hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isConnecting ? "Connecting..." : "Connect"}
        </button>
      </div>
    </div>
  </div>
</div>

{#if isConnecting}
  <AiProcessingBadge overlay message="Connecting to {selectedLabel}..." />
{/if}

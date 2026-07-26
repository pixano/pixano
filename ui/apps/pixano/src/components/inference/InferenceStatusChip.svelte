<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Popover, Portal } from "bits-ui";
  import { Sparkle } from "phosphor-svelte";

  import ConnectToServerModal from "./ConnectToServerModal.svelte";
  import ModelsPanel from "./ModelsPanel.svelte";
  import { inferenceServerStore } from "$lib/stores/inferenceStores.svelte";
  import { IconButton } from "$lib/ui";

  let open = $state(false);
  let showConnectModal = $state(false);

  const connected = $derived(inferenceServerStore.value.connected);

  // Close the popover before opening the modal: the modal is a fixed overlay
  // and must not render inside the popover's containing block.
  const handleRequestConnect = () => {
    open = false;
    showConnectModal = true;
  };
</script>

<Popover.Root bind:open>
  <Popover.Trigger>
    {#snippet child({ props })}
      <span {...props}>
        <IconButton tooltipContent="Inference servers" selected={open} class="h-9 w-9 rounded-lg">
          <Sparkle weight="regular" size={20} />
          <span
            class="absolute bottom-1 right-1 h-2 w-2 rounded-full ring-2 ring-card {connected
              ? 'bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.6)]'
              : 'bg-muted-foreground/40'}"
          ></span>
        </IconButton>
      </span>
    {/snippet}
  </Popover.Trigger>
  <Popover.Portal>
    <Popover.Content
      sideOffset={8}
      align="end"
      class="z-50 flex max-h-[min(70vh,32rem)] w-96 flex-col overflow-hidden rounded-2xl border border-border/50 bg-popover/95 p-0 text-popover-foreground shadow-elevation-2 backdrop-blur-md"
    >
      <ModelsPanel variant="popover" onRequestConnect={handleRequestConnect} />
    </Popover.Content>
  </Popover.Portal>
</Popover.Root>

{#if showConnectModal}
  <Portal>
    <ConnectToServerModal
      onClose={() => (showConnectModal = false)}
      onConnected={() => (showConnectModal = false)}
    />
  </Portal>
{/if}

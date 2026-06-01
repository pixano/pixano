<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { DropdownMenu, Tooltip } from "bits-ui";
  import { CaretDown, FolderOpen } from "phosphor-svelte";
  import { fade } from "svelte/transition";

  import pixanoFavicon from "../assets/favicon.ico";
  import DatasetHeader from "../components/layout/DatasetHeader.svelte";
  import ImportDatasetModal from "../components/library/ImportDatasetModal.svelte";
  import type { LayoutProps } from "./$types";
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import { pixanoLogo } from "$lib/assets";
  import { datasetsStore, themeMode, toggleTheme } from "$lib/stores/appStores.svelte";
  import { getEffectProbeSnapshot, IconButton, ThemeToggle } from "$lib/ui";

  import "./styles.css";

  let { data, children }: LayoutProps = $props();

  const HOME_ROUTE_ID = "/";

  // Populate stores for backward compatibility
  $effect(() => {
    datasetsStore.value = data.datasets;
  });

  const handleEffectDepthExceeded = (event: ErrorEvent) => {
    const message = event.message ?? "";
    if (!message.includes("effect_update_depth_exceeded")) return;
    const topProbes = getEffectProbeSnapshot().slice(0, 12);
    console.groupCollapsed("[pixano-debug] effect_update_depth_exceeded");
    if (event.error) {
      console.error(event.error);
    } else {
      console.error(message);
    }
    if (topProbes.length > 0) {
      console.table(
        topProbes.map((probe) => ({
          effect: probe.label,
          hitsInWindow: probe.hitsInWindow,
          totalHits: probe.totalHits,
          warnLevel: probe.warnLevel,
        })),
      );
    } else {
      console.warn(
        "No effect probes captured yet. Enable verbose probes with PIXANO_EFFECT_DEBUG=1.",
      );
    }
    console.groupEnd();
  };

  $effect(() => {
    window.addEventListener("error", handleEffectDepthExceeded);
    return () => window.removeEventListener("error", handleEffectDepthExceeded);
  });

  let showImportModal = $state(false);

  async function navigateToHome() {
    await goto("/");
  }
</script>

<svelte:head>
  <link rel="icon" type="image/svg" href={pixanoFavicon} />
  <title>Pixano</title>
  <meta name="description" content="Pixano app" />
</svelte:head>

<Tooltip.Provider>
  <div class="app h-screen flex flex-col overflow-hidden bg-background text-foreground font-sans">
    <header
      class="w-full h-16 px-6 flex items-center gap-6 bg-card/80 backdrop-blur-[16px] border-b border-border/40 z-50 shrink-0 shadow-glass-sm"
    >
      <div class="flex items-center shrink-0">
        <IconButton
          onclick={navigateToHome}
          tooltipContent="Go to library"
          class="p-1.5 hover:bg-primary/5 rounded-xl transition-all duration-200"
        >
          <img src={pixanoLogo} alt="Logo Pixano" class="w-8 h-8" />
        </IconButton>
      </div>

      <div class="flex-1 h-full">
        {#if page.route.id !== HOME_ROUTE_ID}
          <div in:fade={{ duration: 300 }} out:fade={{ duration: 200 }} class="h-full w-full">
            <DatasetHeader pageId={page.route.id} />
          </div>
        {/if}
      </div>

      <div class="flex items-center gap-2 shrink-0">
        <!-- File menu -->
        <DropdownMenu.Root>
          <DropdownMenu.Trigger
            class="inline-flex items-center gap-1.5 h-8 px-3 rounded-lg border border-border/60
              bg-background/60 text-sm font-semibold text-foreground hover:bg-accent
              hover:border-border transition-all duration-150 focus-visible:outline-none
              focus-visible:ring-2 focus-visible:ring-ring"
          >
            File
            <CaretDown weight="bold" class="h-3 w-3 text-muted-foreground" />
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              class="z-[300] min-w-[200px] rounded-xl border border-border bg-background/95
                backdrop-blur-sm shadow-lg py-1.5 text-sm"
              sideOffset={6}
              align="end"
            >
              <DropdownMenu.Item
                class="flex items-center gap-2.5 px-3 py-2 cursor-pointer rounded-lg mx-1
                  text-foreground hover:bg-accent focus-visible:bg-accent
                  focus-visible:outline-none transition-colors"
                onSelect={() => {
                  showImportModal = true;
                }}
              >
                <FolderOpen weight="regular" class="h-4 w-4 text-muted-foreground" />
                Import dataset…
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>

        <ThemeToggle mode={themeMode.value} onToggle={toggleTheme} />
      </div>
    </header>

    <main class="flex-1 flex flex-col min-h-0 relative bg-background">
      <div class="flex-1 flex flex-col min-h-0 overflow-hidden">
        {@render children?.()}
      </div>
    </main>
  </div>

  {#if showImportModal}
    <ImportDatasetModal
      onClose={() => {
        showImportModal = false;
      }}
    />
  {/if}
</Tooltip.Provider>

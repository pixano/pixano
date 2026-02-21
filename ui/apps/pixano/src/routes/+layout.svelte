<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { fade } from "svelte/transition";

  import { Tooltip } from "bits-ui";
  import {
    IconButton,
    ThemeToggle,
    getEffectProbeSnapshot,
  } from "$lib/ui";

  import pixanoFavicon from "../assets/favicon.ico";
  import DatasetHeader from "../components/layout/DatasetHeader.svelte";
  import { pixanoLogo } from "$lib/assets";
  import { datasetsStore } from "$lib/stores/appStores.svelte";
  import { themeMode, toggleTheme } from "$lib/stores/appStores.svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import type { LayoutProps } from "./$types";

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
      console.warn("No effect probes captured yet. Enable verbose probes with PIXANO_EFFECT_DEBUG=1.");
    }
    console.groupEnd();
  };

  $effect(() => {
    window.addEventListener("error", handleEffectDepthExceeded);
    return () => window.removeEventListener("error", handleEffectDepthExceeded);
  });

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

    <div class="flex items-center shrink-0">
      <ThemeToggle mode={themeMode.value} onToggle={toggleTheme} />
    </div>
  </header>

  <main class="flex-1 flex flex-col min-h-0 relative bg-background">
    <div class="flex-1 flex flex-col min-h-0 overflow-hidden">
      {@render children?.()}
    </div>
  </main>
</div>
</Tooltip.Provider>

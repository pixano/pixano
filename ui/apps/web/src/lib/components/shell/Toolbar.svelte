<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { ArrowLeftRight, Lock, Moon, PanelRight, Sun, Unlock } from "lucide-svelte";

  import type { PanelState } from "$lib/components/ui/resizable-panel/PanelState.svelte.js";
  import { themeStore } from "$lib/stores/theme.svelte.js";
  import type { WorkspaceManager } from "$lib/workspace/workspaceManager.svelte.js";
  import pixanoLogo from "$lib/assets/pixano.png";
  interface Props {
    manager: WorkspaceManager;
    rightPanel: PanelState;
  }

  let { manager, rightPanel }: Props = $props();

  const isDark = $derived(themeStore.mode === "dark");

  function toggleEditMode() {
    manager.editMode = !manager.editMode;
  }
</script>

<header
  class="bg-background/80 sticky top-0 z-10 flex h-10 shrink-0 items-center gap-2 border-b border-border px-3 backdrop-blur-sm"
>
  <div class="flex flex-1 items-center gap-3">
    <img src={pixanoLogo} alt="Logo Pixano" class="w-7 h-7" />
    <span class="text-sm font-medium text-foreground">Pixano -Workspace</span>
    <span class="text-xs text-muted-foreground">— {manager.presetName}</span>
  </div>

  <div class="flex items-center gap-1.5">
    <span class="mr-1 text-xs text-muted-foreground">
      {manager.widgetCount} widget{manager.widgetCount !== 1 ? "s" : ""}
    </span>

    <button
      onclick={toggleEditMode}
      class="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-xs transition-colors {manager.editMode
        ? 'bg-accent text-accent-foreground'
        : 'text-muted-foreground hover:bg-accent/50'}"
    >
      {#if manager.editMode}
        <Unlock class="h-3.5 w-3.5" />
        <span>Edit</span>
      {:else}
        <Lock class="h-3.5 w-3.5" />
        <span>Locked</span>
      {/if}
    </button>

    <button
      onclick={() => themeStore.toggle()}
      class="flex items-center justify-center rounded-md border border-border p-1 text-xs text-foreground/70 transition-colors hover:bg-accent/50 hover:text-foreground"
      title={isDark ? "Switch to light mode" : "Switch to dark mode"}
    >
      {#if isDark}
        <Sun class="h-3.5 w-3.5" />
      {:else}
        <Moon class="h-3.5 w-3.5" />
      {/if}
    </button>

    <button
      type="button"
      onclick={() => {
        document.cookie = "pixano_ui_version=legacy; max-age=31536000; path=/";
        window.location.href = "/";
      }}
      class="flex items-center justify-center rounded-md border border-border p-1 text-xs text-foreground/70 transition-colors hover:bg-accent/50 hover:text-foreground"
      title="Switch to legacy UI"
    >
      <ArrowLeftRight class="h-3.5 w-3.5" />
    </button>

    <button
      onclick={() => rightPanel.toggle()}
      class="flex items-center justify-center rounded-md border border-border p-1 text-xs transition-colors
				{rightPanel.collapsed
        ? 'text-muted-foreground hover:bg-accent/50'
        : 'bg-accent text-accent-foreground'}"
      title="Toggle right panel"
    >
      <PanelRight class="h-3.5 w-3.5" />
    </button>
  </div>
</header>

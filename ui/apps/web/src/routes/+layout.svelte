<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import "../app.css";

  import type { Snippet } from "svelte";

  import { STORAGE_KEY, themeStore } from "$lib/stores/theme.svelte";

  let { children }: { children: Snippet } = $props();

  $effect(() => {
    document.documentElement.classList.toggle("dark", themeStore.mode === "dark");
    try {
      localStorage.setItem(STORAGE_KEY, themeStore.mode);
    } catch (_) {
      // localStorage blocked — theme works in-session but won't persist
    }
  });
</script>

{@render children()}

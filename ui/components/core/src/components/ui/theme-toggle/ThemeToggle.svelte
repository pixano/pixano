<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Moon, Sun } from "lucide-svelte";

  import { themeMode, toggleTheme } from "../../../lib/stores/themeStore";
</script>

<button
  on:click={toggleTheme}
  class="inline-flex items-center justify-center h-9 w-9 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-colors duration-150"
  title={$themeMode === "dark" ? "Dark mode" : "Light mode"}
>
  {#if $themeMode === "dark"}
    <Moon size={18} />
  {:else}
    <Sun size={18} />
  {/if}
</button>

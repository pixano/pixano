<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Moon, Sun } from "phosphor-svelte";

  interface Props {
    mode: "light" | "dark";
    onToggle: () => void;
  }

  let { mode, onToggle }: Props = $props();
</script>

<button
  onclick={onToggle}
  class="inline-flex items-center justify-center h-9 w-9 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-colors duration-150"
  title={mode === "dark" ? "Dark mode" : "Light mode"}
>
  {#if mode === "dark"}
    <Sun size={22} />
  {:else}
    <Moon size={22} />
  {/if}
</button>

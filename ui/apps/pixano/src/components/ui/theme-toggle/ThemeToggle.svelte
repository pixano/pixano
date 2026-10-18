<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Tooltip } from "bits-ui";
  import { Moon, Sun } from "phosphor-svelte";

  import TooltipContent from "../molecules/TooltipContent.svelte";

  interface Props {
    mode: "light" | "dark";
    onToggle: () => void;
  }

  let { mode, onToggle }: Props = $props();
</script>

<Tooltip.Root>
  <Tooltip.Trigger
    type="button"
    onclick={onToggle}
    class="inline-flex items-center justify-center h-9 w-9 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-colors duration-150"
  >
    {#if mode === "dark"}
      <Sun size={22} />
    {:else}
      <Moon size={22} />
    {/if}
  </Tooltip.Trigger>
  <TooltipContent>
    <p>{mode === "dark" ? "Dark mode" : "Light mode"}</p>
  </TooltipContent>
</Tooltip.Root>

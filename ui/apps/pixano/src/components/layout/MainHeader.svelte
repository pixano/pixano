<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import pixanoLogo from "@pixano/core/src/assets/pixano.png";
</script>

<header class="w-full h-16 px-8 flex items-center bg-background/80 backdrop-blur-md border-b border-border z-20 sticky top-0 shadow-sm">
  <div class="flex gap-3 items-center group cursor-default">
    <div class="p-1.5 rounded-xl bg-primary/5 transition-colors group-hover:bg-primary/10">
      <img src={pixanoLogo} alt="Logo Pixano" class="w-7 h-7" />
    </div>
    <div class="flex flex-col">
      <span class="text-lg font-black text-foreground uppercase tracking-tight leading-none">Pixano</span>
      <span class="text-[10px] text-muted-foreground font-bold uppercase tracking-[0.2em] leading-none mt-0.5">Workspace</span>
    </div>
  </div>
</header>

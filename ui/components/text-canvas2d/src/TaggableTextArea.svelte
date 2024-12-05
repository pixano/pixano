<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { cn } from "@pixano/core";
  import { tagSelectedText } from "./htmlTextTagger";

  const handleClick = () => {
    const metadata = {};
    tagSelectedText({ tagName: "span", metadata, className: cn("text-red-500") });
  };
</script>

<div class={cn("bg-white p-2 flex flex-col gap-2")}>
  <button
    class={cn("bg-slate-800 text-white p-2 rounded-md w-fit")}
    on:click={handleClick}
    id="tagButton">Tag Selected Text</button
  >

  <div id="content" contenteditable="true">
    This is some editable text. Select any text and tag it with custom metadata!
  </div>
</div>

<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { SaveShapeType, TextSpan, TextView, type Shape, type TextSpanType } from "@pixano/core";

  import { SpannableTextView } from "./components";
  import { groupTextSpansByViewId } from "./lib";

  // Exports
  export let selectedItemId: string;
  export let newShape: Shape;
  export let colorScale: (value: string) => string;
  export let textSpans: TextSpan[];
  export let textViews: TextView[];

  const viewRef = { id: textViews[0].id, name: "text" };

  let textSpanAttributes: TextSpanType | null = null;

  $: spansByViewId = groupTextSpansByViewId(textSpans);

  const onTagText = () => {
    if (!textSpanAttributes) return;

    // Changing newShape opens the window for customizing and saving a new
    // anotation in the object inspector
    newShape = {
      viewRef,
      itemId: selectedItemId,
      imageWidth: 0,
      imageHeight: 0,
      status: "saving",
      type: SaveShapeType.textSpan,
      attrs: textSpanAttributes,
    };
  };
</script>

<div class="bg-white p-2 flex flex-col gap-2 h-full overflow-y-auto">
  <button class="bg-primary text-white p-2 rounded-md w-fit" on:click={onTagText} id="tagButton">
    Tag Selected Text
  </button>
  {#each textViews as textView}
    <SpannableTextView
      {textView}
      {colorScale}
      textSpans={spansByViewId[textView.id]}
      bind:textSpanAttributes
    />
  {/each}
</div>

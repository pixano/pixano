<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import {
    SaveShapeType,
    TextSpan,
    TextView,
    type Shape,
    type TextSpanAttributes,
    type TextSpanTypeWithViewRef,
  } from "@pixano/core";

  import { SpannableTextView } from "./components";
  import { groupTextSpansByViewId } from "./lib";

  // Exports
  export let selectedItemId: string;
  export let newShape: Shape;
  export let colorScale: (value: string) => string;
  export let textSpans: TextSpan[];
  export let textViews: TextView[];

  let textSpanAttributes: TextSpanTypeWithViewRef | null = null;

  $: spansByViewId = groupTextSpansByViewId(textSpans);

  const onTagText = () => {
    if (!textSpanAttributes) return;

    const { view_ref, ...textSpanAttrs } = textSpanAttributes;
    // Changing newShape opens the window for customizing and saving a new
    // anotation in the object inspector
    newShape = {
      viewRef: view_ref,
      itemId: selectedItemId,
      imageWidth: 0,
      imageHeight: 0,
      status: "saving",
      type: SaveShapeType.textSpan,
      attrs: textSpanAttrs as TextSpanAttributes,
    };
  };
</script>

<div class="bg-white p-2 flex flex-col gap-2 h-full">
  <button class="bg-primary text-white p-2 rounded-md w-fit" on:click={onTagText} id="tagButton">
    Tag Selected Text
  </button>
  <div class="overflow-y-auto">
    {#each textViews as textView}
      <SpannableTextView
        {textView}
        {colorScale}
        textSpans={spansByViewId[textView.id]}
        bind:textSpanAttributes
      />
    {/each}
  </div>
</div>

<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import {
    BaseSchema,
    ShapeType,
    TextSpan,
    TextView,
    type Shape,
    type TextSpanAttributes,
    type TextSpanTypeWithViewRef,
  } from "$lib/ui";
  import { TEMPORARY_TEXT_SPAN_ID } from "./constants";

  import SpannableTextView from "./SpannableTextView.svelte";
  import { groupTextSpansByViewId } from "./groupTextSpansByViewId";

  
  interface Props {
    // Exports
    selectedItemId: string;
    newShape: Shape;
    colorScale: (value: string) => string;
    textSpans: TextSpan[];
    textViews: TextView[];
    onCreateTemporaryTextSpan?: (textSpan: TextSpan) => void;
    onTextSpanClick?: (textSpan: TextSpan) => void;
    onNewShapeChange?: (shape: Shape) => void;
  }

  let {
    selectedItemId,
    newShape,
    colorScale,
    textSpans,
    textViews,
    onCreateTemporaryTextSpan,
    onTextSpanClick,
    onNewShapeChange
  }: Props = $props();

  let textSpanAttributes: TextSpanTypeWithViewRef | null = $state(null);

  let spansByViewId = $derived(groupTextSpansByViewId(textSpans));

  const onTagText = () => {
    if (!textSpanAttributes) return;

    const { view_ref, ...textSpanAttrs } = textSpanAttributes;

    //temporary TextSpan to keep it highlighted while filling form
    const tempTextSpan = new TextSpan({
      id: TEMPORARY_TEXT_SPAN_ID,
      data: {
        spans_start: textSpanAttributes?.spans_start as number[],
        spans_end: textSpanAttributes?.spans_end as number[],
        mention: textSpanAttributes?.mention as string,
        inference_metadata: {},
        item_ref: { id: selectedItemId, name: "item" },
        entity_ref: { id: "", name: "" },
        view_ref: textSpanAttributes?.view_ref,
        source_ref: { id: "", name: "" },
      },
      table_info: { name: "not_a_table", group: "annotations", base_schema: BaseSchema.TextSpan },
      created_at: "",
      updated_at: "",
    });
    tempTextSpan.ui.displayControl.highlighted = "self";
    onCreateTemporaryTextSpan?.(tempTextSpan);

    // Changing newShape opens the window for customizing and saving a new
    // anotation in the object inspector
    onNewShapeChange?.({
      viewRef: view_ref,
      itemId: selectedItemId,
      imageWidth: 0,
      imageHeight: 0,
      status: "saving",
      type: ShapeType.textSpan,
      attrs: textSpanAttrs as TextSpanAttributes,
    });
  };
</script>

<div class="bg-card p-2 flex flex-col gap-2 h-full">
  <button
    class="bg-primary text-primary-foreground p-2 rounded-md w-fit"
    onclick={onTagText}
    id="tagButton"
  >
    Tag Selected Text
  </button>
  <div class="overflow-y-auto">
    {#each textViews as textView}
      <SpannableTextView
        {textView}
        {colorScale}
        textSpans={spansByViewId[textView.id]}
        bind:textSpanAttributes
        onSpanClick={onTextSpanClick}
      />
    {/each}
  </div>
</div>

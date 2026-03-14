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
    type TextSpanTypeWithViewName,
  } from "$lib/ui";
  import { TEMPORARY_TEXT_SPAN_ID } from "../textCanvas/constants";
  import { groupTextSpansByViewId } from "../textCanvas/groupTextSpansByViewId";
  import TiptapAnnotator from "./TiptapAnnotator.svelte";

  interface Props {
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
    onNewShapeChange,
  }: Props = $props();

  let textSpanAttributes: TextSpanTypeWithViewName | null = $state(null);

  let spansByViewId = $derived(groupTextSpansByViewId(textSpans));

  const onSelectionChange = (attrs: TextSpanTypeWithViewName) => {
    textSpanAttributes = attrs;
  };

  const handleSpanClick = (id: string) => {
    const span = textSpans.find((ts) => ts.id === id);
    if (span) {
      onTextSpanClick?.(span);
    }
  };

  const onTagText = () => {
    if (!textSpanAttributes) return;

    const { view_name, ...textSpanAttrs } = textSpanAttributes;

    const matchingView = textViews.find((v) => v.table_info.name === view_name);
    const viewId = matchingView?.id ?? "";

    const tempTextSpan = new TextSpan({
      id: TEMPORARY_TEXT_SPAN_ID,
      data: {
        spans_start: textSpanAttributes.spans_start,
        spans_end: textSpanAttributes.spans_end,
        mention: textSpanAttributes.mention,
        inference_metadata: {},
        item_id: selectedItemId,
        entity_id: "",
        view_name: textSpanAttributes.view_name ?? "",
        view_id: viewId,
        source_type: "",
        source_name: "",
        source_metadata: "{}",
      },
      table_info: { name: "not_a_table", group: "annotations", base_schema: BaseSchema.TextSpan },
      created_at: "",
      updated_at: "",
    });
    tempTextSpan.ui.displayControl.highlighted = "self";
    onCreateTemporaryTextSpan?.(tempTextSpan);

    onNewShapeChange?.({
      viewRef: { name: view_name, id: viewId },
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
    {#each textViews as textView (textView.id)}
      <TiptapAnnotator
        {textView}
        {colorScale}
        textSpans={spansByViewId[textView.id]}
        {onSelectionChange}
        onSpanClick={handleSpanClick}
      />
    {/each}
  </div>
</div>

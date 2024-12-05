<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { cn, NamedEntity } from "@pixano/core";
  import { getNewNamedEntity } from "./getNewNamedEntity";
  import { getSelectedText } from "./getSelectedText";
  import { getSelection } from "./getSelection";
  import { tagSelectedText } from "./htmlTextTagger";

  let namedEntities: NamedEntity[] = [];

  // To avoid importing nanoid package
  // TODO: update objectsApi
  let namedEntityId = 0;

  const handleClick = () => {
    const { selection, range } = getSelection();
    const selectedText = getSelectedText(selection);

    const newNamedEntity = getNewNamedEntity(namedEntityId.toString(), selectedText);
    ++namedEntityId;

    namedEntities = [...namedEntities, newNamedEntity];

    newNamedEntity.ui.bgColor = "black";

    const metadata = {
      id: newNamedEntity.id,
      bgColor: newNamedEntity.ui.bgColor,
    };

    tagSelectedText({
      selection,
      range,
      selectedText,
      tagName: "span",
      metadata,
      className: `text-white rounded-md p-1 bg-${newNamedEntity.ui.bgColor}`,
    });
  };
</script>

<div class={cn("bg-white p-2 flex flex-col gap-2")}>
  <button
    class={cn("bg-red-800 text-white p-2 rounded-md w-fit")}
    on:click={handleClick}
    id="tagButton">Tag Selected Text</button
  >

  <div id="content" contenteditable="true">
    This is some editable text. Select any text and tag it with custom metadata!
  </div>
</div>

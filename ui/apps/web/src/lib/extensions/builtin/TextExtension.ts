/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import TextWidget from "$lib/components/widgets/TextWidget.svelte";

import { WidgetExtension } from "../WidgetExtension.js";

export const TextExtension = WidgetExtension.create({
  name: "text",
  label: "Rich Text",
  icon: "file-text",
  priority: 80,
  defaultLayout: { x: 0, y: 0, w: 4, h: 4, minW: 2, minH: 2 },
  component: TextWidget,
  addOptions: () => ({
    editable: true,
  }),
  addStorage: () => ({
    editorInstance: null,
  }),
  // The text widget has no per-record fetch; it just claims any `Text`
  // view and renders an editor pane.
  addRecordSeed: ({ viewName, viewDef }) =>
    viewDef.base === "Text"
      ? Promise.resolve({ title: viewName, options: {} })
      : Promise.resolve(null),
});

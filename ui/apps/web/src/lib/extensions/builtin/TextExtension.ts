/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { WidgetExtension } from "../WidgetExtension.js";
import TextWidget from "$lib/components/widgets/TextWidget.svelte";

export const TextExtension = WidgetExtension.create({
  name: "text",
  label: "Rich Text",
  icon: "file-text",
  priority: 80,
  defaultLayout: { x: 0, y: 0, w: 4, h: 4, minW: 2, minH: 2 },
  component: TextWidget,
  addOptions: () => ({
    datasetId: "",
    recordId: "",
    viewId: "",
    viewName: "",
    editable: true,
  }),
  addStorage: () => ({
    editorInstance: null,
  }),
  addRecordSeed: async ({ datasetId, recordId, viewName, viewDef, gateway }) => {
    if (viewDef.base !== "Text") return null;

    const text = await gateway.loadTextByLogicalName(datasetId, recordId, viewName);

    return {
      title: viewName,
      options: { datasetId, recordId, viewId: text?.id ?? "", viewName },
      // Without this the widget rendered "No Text Data" on every record: the
      // seed claimed the view but never fetched what fills it.
      data: { content: text?.content ?? "" },
      // Declares the view to the shared seed loaders, exactly as the image and
      // point-cloud extensions do, so text annotations resolve against it.
      view: { id: text?.id ?? "", logicalName: viewName, width: 0, height: 0 },
    };
  },
});

/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { answerChoicesToCheckboxsState } from "./answerChoicesToCheckboxsState";

export const deserializeMessageContent = (content: string | null) => {
  if (content === null) {
    return { checked: [], explanations: "" };
  }

  const regex = /^\[\[(.*)\]\]\s*(.*)$/;
  const match = content.match(regex);

  if (match) {
    const choices = match[1] ? match[1].split(",").map((c) => c.trim()) : [];
    const checked = answerChoicesToCheckboxsState(choices);

    const explanations = match[2].trim();
    return { checked, explanations };
  }

  // Content is plain text (e.g. typed via the text input) — treat as no selection
  return { checked: [], explanations: content };
};

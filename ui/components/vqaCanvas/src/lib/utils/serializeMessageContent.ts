/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export const serializeMessageContent = ({
  choices,
  explanations,
}: {
  choices: string[];
  explanations: string;
}) => `[[${choices.join(",")}]] ${explanations}`;

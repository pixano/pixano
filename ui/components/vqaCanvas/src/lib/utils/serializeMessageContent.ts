/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export const serializeMessageContent = ({
  choices,
  explanation,
}: {
  choices: string[];
  explanation: string;
}) => `[[${choices.join(",")}]] ${explanation}`;

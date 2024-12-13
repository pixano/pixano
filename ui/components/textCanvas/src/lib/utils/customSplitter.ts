/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

const SPLITTER = "";

export const customSplitter = (text: string) => text.split(SPLITTER);
export const customJoiner = (splittedText: string[]) => splittedText.join(SPLITTER);

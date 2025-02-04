/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export interface ContentChangeEvent {
  answerId: string;
  newContent: string;
  newChoices: string[];
  explanation: string;
}

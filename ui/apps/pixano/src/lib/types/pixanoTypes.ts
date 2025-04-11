/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export type DatasetTableStore = {
  currentPage: number;
  pageSize: number;
  query?: {
    model: string;
    search: string;
  };
  where?: string;
};

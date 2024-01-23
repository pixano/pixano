export type DatasetTableStore = {
  currentPage: number;
  pageSize: number;
  query: {
    model: string;
    search: string;
  };
};

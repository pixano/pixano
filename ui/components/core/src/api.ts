/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Imports
import {
  type Dataset,
  DatasetInfo,
  type DatasetInfoType,
  //type DatasetItems,
  DatasetItem,
  Item,
  type Schema,
  type DatasetItemType,
  DatasetBrowser,
  type DatasetBrowserType,
} from "./lib/types/datasetTypes";

// Exports
export async function getDatasetsInfo(): Promise<Array<DatasetInfo>> {
  let datasets_raw: Array<DatasetInfoType>;
  let datasets: Array<DatasetInfo>;

  try {
    const response = await fetch("/datasets/info");
    if (response.ok) {
      datasets_raw = (await response.json()) as Array<DatasetInfoType>;
      datasets = datasets_raw.map((ds_raw) => {
        return new DatasetInfo(ds_raw);
      });
    } else {
      datasets = [];
      console.log(
        "api.getDatasetsInfo -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
    datasets = [];
    console.log("api.getDatasetsInfo -", e);
  }

  return datasets;
}

// UNUSED
// export async function getDatasetInfo(datasetId: string): Promise<DatasetInfo> {
//   let dataset: DatasetInfo;

//   try {
//     const response = await fetch(`/datasets/info/${datasetId}`);
//     if (response.ok) {
//       dataset = (await response.json()) as DatasetInfo;
//     } else {
//       dataset = {} as DatasetInfo;
//       console.log("api.getDatasetInfo -", response.status, response.statusText, await response.text());
//     }
//   } catch (e) {
//     dataset = {} as DatasetInfo;
//     console.log("api.getDatasetInfo -", e);
//   }
//   return dataset;
// }

export async function getDataset(datasetId: string): Promise<Dataset> {
  let dataset;

  try {
    const response = await fetch(`/datasets/${datasetId}`);
    if (response.ok) {
      dataset = (await response.json()) as Dataset;
    } else {
      dataset = {} as Dataset;
      console.log("api.getDataset -", response.status, response.statusText, await response.text());
    }
  } catch (e) {
    dataset = {} as Dataset;
    console.log("api.getDataset -", e);
  }
  return dataset;
}

export async function getBrowser(
  datasetId: string,
  page: number = 1,
  size: number = 100,
  query: Record<string, string> | undefined,
): Promise<DatasetBrowser> {
  let datasetItems: DatasetBrowser;
  let datasetItems_raw: DatasetBrowserType;

  let query_qparams = "";
  if (query && query.model !== "" && query.search !== "") {
    query_qparams = `&query=${query.search}&table=${query.model}`;
  }
  try {
    const response = await fetch(
      `/browser/${datasetId}/?page=${page}&size=${size}${query_qparams}`,
    );
    if (response.ok) {
      datasetItems_raw = (await response.json()) as DatasetBrowserType;
      datasetItems = new DatasetBrowser(datasetItems_raw);
    } else {
      datasetItems = {} as DatasetBrowser;
      console.log("api.getBrowser -", response.status, response.statusText, await response.text());
    }
  } catch (e) {
    datasetItems = {} as DatasetBrowser;
    console.log("api.getBrowser -", e);
  }

  return datasetItems;
}

// Request API to get all the items ids for a given dataset
export async function getDatasetItemsIds(datasetId: string): Promise<Array<string>> {
  const datasetItemsIds: string[] = [];
  const page_size = 1000;
  for (let skip = 0; ; skip += page_size) {
    try {
      const response = await fetch(`/items/${datasetId}/?limit=${page_size}&skip=${skip}`);
      if (response.ok) {
        const res = (await response.json()) as Item[];
        datasetItemsIds.push(...res.map((item) => item.id));
        if (res && res.length < page_size) {
          break; //just to avoid 404 error log (will still appear if num items % page_size == 0)
        }
      } else {
        if (response.status != 404)
          console.log(
            "api.getDatasetItemsIds -",
            response.status,
            response.statusText,
            await response.text(),
          ); // Handle API errors
        break;
      }
    } catch (e) {
      console.log("api.getDatasetItemsIds -", e); // Handle other errors
    }
  }
  return datasetItemsIds;
}

//UNUSED
// export async function searchDatasetItems(
//   datasetId: string,
//   query: Record<string, string>,
//   page: number = 1,
//   size: number = 100,
// ): Promise<DatasetItems> {
//   let datasetItems: DatasetItems | undefined;
//   try {
//     const response = await fetch(`/datasets/${datasetId}/search?page=${page}&size=${size}`, {
//       headers: {
//         Accept: "application/json",
//         "Content-Type": "application/json",
//       },
//       body: JSON.stringify(query),
//       method: "POST",
//     });
//     if (response.ok) {
//       datasetItems = (await response.json()) as DatasetItems;
//     } else {
//       throw new Error("api.searchDatasetItems");
//     }
//   } catch (e) {
//     throw new Error("api.searchDatasetItems");
//   }
//   return datasetItems;
// }

export async function getDatasetItem(datasetId: string, itemId: string): Promise<DatasetItem> {
  let item_raw: DatasetItemType | undefined;
  let item: DatasetItem | undefined;
  const start = Date.now();
  try {
    const response = await fetch(`/dataset_items/${datasetId}/${itemId}`);

    if (response.ok) {
      item_raw = (await response.json()) as DatasetItem;
      item = new DatasetItem(item_raw);
    } else {
      item = {} as DatasetItem;
      console.log(
        "api.getDatasetItem -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
    item = {} as DatasetItem;
    console.log("api.getDatasetItem -", e);
  }
  console.log("api.getDatasetItem - Done in", Date.now() - start);
  return item;
}

export async function getItemEmbeddings(
  datasetId: string,
  itemId: string,
  modelId: string,
): Promise<DatasetItem> {
  let item: DatasetItem | undefined;

  try {
    const response = await fetch(`/datasets/${datasetId}/items/${itemId}/embeddings/${modelId}`);
    if (response.ok) {
      item = (await response.json()) as DatasetItem;
    } else {
      item = {} as DatasetItem;
      console.log(
        "api.getItemEmbeddings -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
    item = {} as DatasetItem;
    console.log("api.getItemEmbeddings -", e);
  }
  return item;
}

// export async function postDatasetItem(datasetId: string, item: DatasetItemSave) {
//   try {
//     const response = await fetch(`/datasets/${datasetId}/items/${item.id}`, {
//       headers: {
//         Accept: "application/json",
//         "Content-Type": "application/json",
//       },
//       body: JSON.stringify(item),
//       method: "POST",
//     });
//     if (response.ok) {
//       console.log(
//         "api.postDatasetItem -",
//         response.status,
//         response.statusText,
//         await response.text(),
//       );
//     }
//   } catch (e) {
//     console.log("api.postDatasetItem -", e);
//   }
// }

export async function deleteSchema(route: string, ds_id: string, sch: Schema, no_table: boolean) {
  const url = no_table
    ? `/${route}/${ds_id}/${sch.id}`
    : `/${route}/${ds_id}/${sch.table_info.name}/${sch.id}`;
  try {
    const response = await fetch(url, {
      method: "DELETE",
    });
    if (!response.ok) {
      console.log(
        "api.deleteSchema -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
    console.log("api.deleteSchema -", e);
  }
}

export async function addSchema(route: string, ds_id: string, sch: Schema, no_table: boolean) {
  const url = no_table
    ? `/${route}/${ds_id}/${sch.id}`
    : `/${route}/${ds_id}/${sch.table_info.name}/${sch.id}`;
  try {
    const response = await fetch(url, {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      method: "POST",
      body: JSON.stringify(sch),
    });
    if (!response.ok) {
      console.log("api.addSchema -", response.status, response.statusText, await response.text());
    }
  } catch (e) {
    console.log("api.addSchema -", e);
  }
}

export async function updateSchema(route: string, ds_id: string, sch: Schema, no_table: boolean) {
  const url = no_table
    ? `/${route}/${ds_id}/${sch.id}`
    : `/${route}/${ds_id}/${sch.table_info.name}/${sch.id}`;
  try {
    const response = await fetch(url, {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      method: "PUT",
      body: JSON.stringify(sch),
    });
    if (!response.ok) {
      console.log(
        "api.updateSchema -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
    console.log("api.updateSchema -", e);
  }
}

export async function getModels(): Promise<Array<string>> {
  let models: Array<string> | undefined;

  try {
    const response = await fetch("/models");
    if (response.ok) {
      models = (await response.json()) as Array<string>;
    } else {
      models = [];
      console.log("api.getModels -", response.status, response.statusText, await response.text());
    }
  } catch (e) {
    models = [];
    console.log("api.getModels -", e);
  }

  return models;
}

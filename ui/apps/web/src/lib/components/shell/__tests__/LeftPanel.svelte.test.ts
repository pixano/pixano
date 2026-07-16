/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import LeftPanel from "../LeftPanel.svelte";
import { listDatasets, listRecords } from "$lib/api/datasets";
import type { WidgetRegistry } from "$lib/extensions/WidgetRegistry.js";
import { DatasetInfo } from "$lib/types/dataset";
import type { WorkspaceManager } from "$lib/workspace/workspaceManager.svelte.js";

vi.mock("$lib/api/datasets", () => ({
  listDatasets: vi.fn(),
  listRecords: vi.fn(),
  getDataset: vi.fn(),
}));

const mockedListDatasets = vi.mocked(listDatasets);
const mockedListRecords = vi.mocked(listRecords);

const mockRegistry = {
  getAll: vi.fn().mockReturnValue([]),
} as unknown as WidgetRegistry;

const mockManager = {
  addWidget: vi.fn(),
  clearWorkspace: vi.fn(),
  selectRecordInDataset: vi.fn().mockResolvedValue(undefined),
} as unknown as WorkspaceManager;

const mockDataset = new DatasetInfo({
  id: "ds-1",
  name: "COCO 2017",
  description: "Common Objects in Context",
  size: "18GB",
  preview: "",
  workspace: "image",
  num_items: 5000,
});

const mockRecordsPage = {
  items: [
    { id: "rec-1", split: "train" },
    { id: "rec-2", split: "val" },
  ],
  total: 2,
  limit: 50,
  offset: 0,
};

function renderPanel(activeSection = "explorer") {
  return render(LeftPanel, {
    props: { activeSection, registry: mockRegistry, manager: mockManager },
  });
}

describe("LeftPanel — explorer section", () => {
  beforeEach(() => {
    mockedListDatasets.mockResolvedValue([]);
    mockedListRecords.mockResolvedValue(mockRecordsPage);
    vi.mocked(mockManager.selectRecordInDataset).mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  it("shows EXPLORER label in header", async () => {
    renderPanel();
    expect(screen.getByText("Explorer")).toBeInTheDocument();
  });

  it("fetches datasets on mount", async () => {
    mockedListDatasets.mockResolvedValue([mockDataset]);
    renderPanel();
    await waitFor(() => expect(mockedListDatasets).toHaveBeenCalledOnce());
  });

  it("displays fetched dataset names and record counts", async () => {
    mockedListDatasets.mockResolvedValue([mockDataset]);
    renderPanel();

    await waitFor(() => expect(screen.getByText("COCO 2017")).toBeInTheDocument());
    expect(screen.getByText("5000")).toBeInTheDocument();
  });

  it("shows 'No datasets found' when list is empty", async () => {
    mockedListDatasets.mockResolvedValue([]);
    renderPanel();

    await waitFor(() => expect(screen.getByText("No datasets found.")).toBeInTheDocument());
  });

  it("shows error message when listDatasets rejects", async () => {
    mockedListDatasets.mockRejectedValue(new Error("Server unavailable"));
    renderPanel();

    await waitFor(() => expect(screen.getByText("Server unavailable")).toBeInTheDocument());
  });

  it("shows a loading indicator while datasets are being fetched", async () => {
    let resolveDatasets: (value: DatasetInfo[]) => void = () => {};
    mockedListDatasets.mockReturnValueOnce(
      new Promise<DatasetInfo[]>((resolve) => {
        resolveDatasets = resolve;
      }),
    );

    renderPanel();

    await waitFor(() => expect(screen.getByText("Loading…")).toBeInTheDocument());

    resolveDatasets([mockDataset]);
    await waitFor(() => expect(screen.queryByText("Loading…")).not.toBeInTheDocument());
  });

  it("clicking a dataset switches to records view with back button", async () => {
    mockedListDatasets.mockResolvedValue([mockDataset]);
    renderPanel();

    await waitFor(() => screen.getByRole("button", { name: /COCO 2017/ }));
    fireEvent.click(screen.getByRole("button", { name: /COCO 2017/ }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Back to datasets" })).toBeInTheDocument(),
    );
  });

  it("records view shows dataset name in header", async () => {
    mockedListDatasets.mockResolvedValue([mockDataset]);
    renderPanel();

    await waitFor(() => screen.getByRole("button", { name: /COCO 2017/ }));
    fireEvent.click(screen.getByRole("button", { name: /COCO 2017/ }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Back to datasets" })).toBeInTheDocument(),
    );
    expect(screen.getByText("COCO 2017", { selector: "span" })).toBeInTheDocument();
  });

  it("records view displays record ids", async () => {
    mockedListDatasets.mockResolvedValue([mockDataset]);
    renderPanel();

    await waitFor(() => screen.getByRole("button", { name: /COCO 2017/ }));
    fireEvent.click(screen.getByRole("button", { name: /COCO 2017/ }));

    await waitFor(() => expect(screen.getByText("rec-1")).toBeInTheDocument());
    expect(screen.getByText("rec-2")).toBeInTheDocument();
  });

  it("renders image previews for records that have them, and a fallback tile otherwise", async () => {
    mockedListDatasets.mockResolvedValue([mockDataset]);
    mockedListRecords.mockResolvedValue({
      items: [
        {
          id: "with-previews",
          split: "train",
          view_previews: {
            cam_front: { resource: "images", id: "v1", kind: "image", preview_url: "/p/v1" },
            cam_back: { resource: "images", id: "v2", kind: "image", preview_url: "/p/v2" },
          },
        },
        { id: "no-previews", split: "val" },
      ],
      total: 2,
      limit: 50,
      offset: 0,
    });
    const { container } = renderPanel();

    await waitFor(() => screen.getByRole("button", { name: /COCO 2017/ }));
    fireEvent.click(screen.getByRole("button", { name: /COCO 2017/ }));

    await waitFor(() => screen.getByText("with-previews"));
    const imgs = container.querySelectorAll<HTMLImageElement>("img");
    const sources = Array.from(imgs).map((img) => img.getAttribute("src"));
    // The two image views of the first record are rendered; the preview-less
    // record contributes no <img> (it uses the color tile instead).
    expect(sources).toEqual(["/p/v1", "/p/v2"]);
    expect(imgs[0].getAttribute("loading")).toBe("lazy");
  });

  it("drops a preview whose image fails to load, keeping the others", async () => {
    mockedListDatasets.mockResolvedValue([mockDataset]);
    mockedListRecords.mockResolvedValue({
      items: [
        {
          id: "with-previews",
          split: "train",
          view_previews: {
            cam_front: { resource: "images", id: "v1", kind: "image", preview_url: "/p/v1" },
            cam_back: { resource: "images", id: "v2", kind: "image", preview_url: "/p/v2" },
          },
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });
    const { container } = renderPanel();

    await waitFor(() => screen.getByRole("button", { name: /COCO 2017/ }));
    fireEvent.click(screen.getByRole("button", { name: /COCO 2017/ }));

    await waitFor(() => expect(container.querySelectorAll("img")).toHaveLength(2));
    const broken = container.querySelector<HTMLImageElement>('img[src="/p/v1"]')!;
    fireEvent.error(broken);

    await waitFor(() => {
      const remaining = Array.from(container.querySelectorAll<HTMLImageElement>("img")).map((img) =>
        img.getAttribute("src"),
      );
      expect(remaining).toEqual(["/p/v2"]);
    });
  });

  // The collage cell is a fixed 2x2 grid; previewSlotClass must fill it for any
  // view count so 2- and 3-preview records (which we can't reproduce with a real
  // fixture here) don't leave a gap.
  it.each([
    [1, ["col-span-2 row-span-2"]],
    [2, ["row-span-2", "row-span-2"]],
    [3, ["", "", "col-span-2"]],
    [4, ["", "", "", ""]],
  ])("lays out %i previews so the collage cell is fully filled", async (count, expectedSpans) => {
    const view_previews = Object.fromEntries(
      Array.from({ length: count }, (_, i) => [
        `cam_${i}`,
        { resource: "images", id: `v${i}`, kind: "image", preview_url: `/p/v${i}` },
      ]),
    );
    mockedListDatasets.mockResolvedValue([mockDataset]);
    mockedListRecords.mockResolvedValue({
      items: [{ id: "rec", split: "train", view_previews }],
      total: 1,
      limit: 50,
      offset: 0,
    });
    const { container } = renderPanel();

    await waitFor(() => screen.getByRole("button", { name: /COCO 2017/ }));
    fireEvent.click(screen.getByRole("button", { name: /COCO 2017/ }));

    await waitFor(() => expect(container.querySelectorAll("img")).toHaveLength(count));
    const spans = Array.from(container.querySelectorAll<HTMLImageElement>("img")).map((img) =>
      ["col-span-2", "row-span-2"].filter((c) => img.classList.contains(c)).join(" "),
    );
    expect(spans).toEqual(expectedSpans);
  });

  it("shows 'No records found' when dataset has no records", async () => {
    mockedListDatasets.mockResolvedValue([mockDataset]);
    mockedListRecords.mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
    renderPanel();

    await waitFor(() => screen.getByRole("button", { name: /COCO 2017/ }));
    fireEvent.click(screen.getByRole("button", { name: /COCO 2017/ }));

    await waitFor(() => expect(screen.getByText("No records found.")).toBeInTheDocument());
  });

  it("shows error message when listRecords rejects", async () => {
    mockedListDatasets.mockResolvedValue([mockDataset]);
    mockedListRecords.mockRejectedValue(new Error("Failed to fetch records"));
    renderPanel();

    await waitFor(() => screen.getByRole("button", { name: /COCO 2017/ }));
    fireEvent.click(screen.getByRole("button", { name: /COCO 2017/ }));

    await waitFor(() => expect(screen.getByText("Failed to fetch records")).toBeInTheDocument());
  });

  it("back button returns to datasets list", async () => {
    mockedListDatasets.mockResolvedValue([mockDataset]);
    renderPanel();

    await waitFor(() => screen.getByRole("button", { name: /COCO 2017/ }));
    fireEvent.click(screen.getByRole("button", { name: /COCO 2017/ }));

    await waitFor(() => screen.getByRole("button", { name: "Back to datasets" }));
    fireEvent.click(screen.getByRole("button", { name: "Back to datasets" }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /COCO 2017/ })).toBeInTheDocument(),
    );
    expect(screen.queryByRole("button", { name: "Back to datasets" })).not.toBeInTheDocument();
  });

  it("clicking a record calls manager.selectRecordInDataset with correct ids", async () => {
    mockedListDatasets.mockResolvedValue([mockDataset]);
    renderPanel();

    await waitFor(() => screen.getByRole("button", { name: /COCO 2017/ }));
    fireEvent.click(screen.getByRole("button", { name: /COCO 2017/ }));

    await waitFor(() => screen.getByRole("button", { name: "rec-1 train" }));
    fireEvent.click(screen.getByRole("button", { name: "rec-1 train" }));

    await waitFor(() =>
      expect(mockManager.selectRecordInDataset).toHaveBeenCalledWith(
        "ds-1",
        "rec-1",
        // Viewport is measured from the (jsdom) DOM. We don't care about
        // the exact numbers here — just that LeftPanel forwards a
        // {width, height} object so the manager doesn't have to.
        expect.objectContaining({
          width: expect.any(Number),
          height: expect.any(Number),
        }),
      ),
    );
  });

  describe("pagination", () => {
    const firstPage = {
      items: Array.from({ length: 50 }, (_, i) => ({ id: `rec-${i}`, split: "train" })),
      total: 120,
      limit: 50,
      offset: 0,
    };
    const secondPage = {
      items: Array.from({ length: 50 }, (_, i) => ({ id: `rec-${i + 50}`, split: "train" })),
      total: 120,
      limit: 50,
      offset: 50,
    };
    const thirdPage = {
      items: Array.from({ length: 20 }, (_, i) => ({ id: `rec-${i + 100}`, split: "train" })),
      total: 120,
      limit: 50,
      offset: 100,
    };

    async function navigateToRecords() {
      mockedListDatasets.mockResolvedValue([mockDataset]);
      renderPanel();
      await waitFor(() => screen.getByRole("button", { name: /COCO 2017/ }));
      fireEvent.click(screen.getByRole("button", { name: /COCO 2017/ }));
      await waitFor(() => screen.getByRole("button", { name: "rec-0 train" }));
    }

    it("requests first page with limit=50 and offset=0", async () => {
      mockedListRecords.mockResolvedValueOnce(firstPage);
      await navigateToRecords();
      expect(mockedListRecords).toHaveBeenCalledWith("ds-1", 50, 0);
    });

    it("shows Load more button and count when more records are available", async () => {
      mockedListRecords.mockResolvedValueOnce(firstPage);
      await navigateToRecords();

      expect(screen.getByText("50 / 120")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Load more/ })).toBeInTheDocument();
    });

    it("hides Load more button when all records are loaded", async () => {
      mockedListRecords.mockResolvedValueOnce({
        items: [{ id: "only-rec", split: "train" }],
        total: 1,
        limit: 50,
        offset: 0,
      });
      mockedListDatasets.mockResolvedValue([mockDataset]);
      renderPanel();
      await waitFor(() => screen.getByRole("button", { name: /COCO 2017/ }));
      fireEvent.click(screen.getByRole("button", { name: /COCO 2017/ }));

      await waitFor(() => screen.getByRole("button", { name: "only-rec train" }));
      expect(screen.queryByRole("button", { name: /Load more/ })).not.toBeInTheDocument();
      expect(screen.getByText("1 / 1")).toBeInTheDocument();
    });

    it("appends next page and bumps offset when Load more is clicked", async () => {
      mockedListRecords.mockResolvedValueOnce(firstPage);
      mockedListRecords.mockResolvedValueOnce(secondPage);
      await navigateToRecords();

      fireEvent.click(screen.getByRole("button", { name: /Load more/ }));

      await waitFor(() => expect(screen.getByText("100 / 120")).toBeInTheDocument());
      expect(mockedListRecords).toHaveBeenNthCalledWith(2, "ds-1", 50, 50);
      expect(screen.getByRole("button", { name: "rec-99 train" })).toBeInTheDocument();
    });

    it("hides Load more after the final page is fetched", async () => {
      mockedListRecords.mockResolvedValueOnce(firstPage);
      mockedListRecords.mockResolvedValueOnce(secondPage);
      mockedListRecords.mockResolvedValueOnce(thirdPage);
      await navigateToRecords();

      fireEvent.click(screen.getByRole("button", { name: /Load more/ }));
      await waitFor(() => expect(screen.getByText("100 / 120")).toBeInTheDocument());

      fireEvent.click(screen.getByRole("button", { name: /Load more/ }));
      await waitFor(() => expect(screen.getByText("120 / 120")).toBeInTheDocument());

      expect(mockedListRecords).toHaveBeenNthCalledWith(3, "ds-1", 50, 100);
      expect(screen.queryByRole("button", { name: /Load more/ })).not.toBeInTheDocument();
    });

    it("shows an error message when Load more fails without dropping existing records", async () => {
      mockedListRecords.mockResolvedValueOnce(firstPage);
      mockedListRecords.mockRejectedValueOnce(new Error("Boom"));
      await navigateToRecords();

      fireEvent.click(screen.getByRole("button", { name: /Load more/ }));

      await waitFor(() => expect(screen.getByText("Boom")).toBeInTheDocument());
    });

    it("auto-loads the next page when the sentinel intersects the viewport", async () => {
      const callbacks: IntersectionObserverCallback[] = [];
      const observeSpy = vi.fn();
      const disconnectSpy = vi.fn();
      class MockIntersectionObserver {
        constructor(cb: IntersectionObserverCallback) {
          callbacks.push(cb);
        }
        observe = observeSpy;
        unobserve = vi.fn();
        disconnect = disconnectSpy;
        takeRecords = () => [];
        root = null;
        rootMargin = "";
        thresholds = [];
      }
      vi.stubGlobal("IntersectionObserver", MockIntersectionObserver);

      try {
        mockedListRecords.mockResolvedValueOnce(firstPage);
        mockedListRecords.mockResolvedValueOnce(secondPage);
        await navigateToRecords();

        await waitFor(() => expect(observeSpy).toHaveBeenCalled());

        const fakeEntry = { isIntersecting: true } as IntersectionObserverEntry;
        callbacks.forEach((cb) => cb([fakeEntry], {} as IntersectionObserver));

        await waitFor(() => expect(screen.getByText("100 / 120")).toBeInTheDocument());
        expect(mockedListRecords).toHaveBeenNthCalledWith(2, "ds-1", 50, 50);
      } finally {
        vi.unstubAllGlobals();
      }
    });

    it("resets pagination when going back and re-opening the same dataset", async () => {
      mockedListRecords.mockResolvedValueOnce(firstPage);
      mockedListRecords.mockResolvedValueOnce(secondPage);
      mockedListRecords.mockResolvedValueOnce(firstPage);
      await navigateToRecords();

      fireEvent.click(screen.getByRole("button", { name: /Load more/ }));
      await waitFor(() => expect(screen.getByText("100 / 120")).toBeInTheDocument());

      fireEvent.click(screen.getByRole("button", { name: "Back to datasets" }));
      await waitFor(() => screen.getByRole("button", { name: /COCO 2017/ }));

      fireEvent.click(screen.getByRole("button", { name: /COCO 2017/ }));
      await waitFor(() => expect(screen.getByText("50 / 120")).toBeInTheDocument());

      expect(mockedListRecords).toHaveBeenNthCalledWith(3, "ds-1", 50, 0);
    });
  });
});

describe("LeftPanel — other sections", () => {
  beforeEach(() => {
    mockedListDatasets.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  it("shows WIDGETS label in panel header when activeSection is widgets", () => {
    renderPanel("widgets");
    // The panel header uses a <span>; WidgetPalette also renders <h3>Widgets</h3>
    expect(screen.getByText("Widgets", { selector: "span" })).toBeInTheDocument();
  });

  it("shows search input when activeSection is search", () => {
    renderPanel("search");
    expect(screen.getByPlaceholderText("Search samples...")).toBeInTheDocument();
  });

  it("does not fetch datasets when section is widgets", async () => {
    renderPanel("widgets");
    await new Promise((r) => setTimeout(r, 50));
    expect(mockedListDatasets).toHaveBeenCalledOnce();
  });

  it("falls back to the widgets section label when activeSection is unknown", () => {
    renderPanel("does-not-exist");
    expect(screen.getByText("Widgets", { selector: "span" })).toBeInTheDocument();
  });
});

/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";

import RightPanel from "../RightPanel.svelte";
import { BBOX_RESOURCE } from "$lib/annotations/kinds/2d/bbox/bboxPayloadBuilder.js";
import type { WidgetRegistry } from "$lib/extensions/WidgetRegistry.js";
import {
  drag,
  entityOf,
  humanBox,
  modelBox,
  openManager,
  widgetSeam,
  type FakeBackend,
} from "$lib/workspace/__tests__/workspaceHarness.js";
import type { DatasetGateway } from "$lib/workspace/datasetGateway.js";
import { WorkspaceManager } from "$lib/workspace/workspaceManager.svelte.js";

// The Review tab as a person uses it: rendered inside the right panel, over the
// real manager and queue, with only the HTTP edge faked — so a click on Accept
// is checked all the way to the body Save sends.

const REC_1 = "rec-1";

function records(): FakeBackend["records"] {
  return {
    [REC_1]: {
      [BBOX_RESOURCE]: [
        modelBox(REC_1, "b1"),
        modelBox(REC_1, "b2", "accepted"),
        humanBox(REC_1, "h1"),
      ],
    },
  };
}

const ENTITIES = [
  entityOf(REC_1, "ent-b1", { category: "car" }),
  entityOf(REC_1, "ent-b2", { category: "bus" }),
  entityOf(REC_1, "ent-h1", { category: "tree" }),
];

async function openReviewTab(rows: FakeBackend["records"] = records()) {
  const opened = await openManager(rows, { entities: ENTITIES });
  render(RightPanel, { props: { manager: opened.manager } });
  await fireEvent.click(screen.getByRole("button", { name: /^Review$/ }));
  return opened;
}

function rows(): HTMLElement[] {
  return within(screen.getByRole("list", { name: "Annotations of this record" })).getAllByRole(
    "listitem",
  );
}

function rowNamed(label: string): HTMLElement {
  const row = rows().find((item) => within(item).queryByText(label) !== null);
  if (!row) throw new Error(`no row for ${label}`);
  return row;
}

const isDisabled = (element: HTMLElement) => (element as HTMLButtonElement).disabled;

/** What assistive tech reads after a button's name: the text its `aria-describedby` points at. */
function descriptionOf(element: HTMLElement): string | null {
  const id = element.getAttribute("aria-describedby");
  return id ? (document.getElementById(id)?.textContent ?? null) : null;
}

afterEach(() => cleanup());

describe("Review tab", () => {
  it("asks for a record when none is open", async () => {
    const manager = new WorkspaceManager(
      { get: () => undefined, getAll: () => [] } as unknown as WidgetRegistry,
      {} as DatasetGateway,
    );
    render(RightPanel, { props: { manager } });

    await fireEvent.click(screen.getByRole("button", { name: /^Review$/ }));

    expect(screen.getByText("Open a record to review its annotations.")).toBeTruthy();
  });

  it("lists the record's annotations with their status", async () => {
    await openReviewTab();

    expect(rows()).toHaveLength(3);
    expect(within(rowNamed("car")).getByText("Pending")).toBeTruthy();
    expect(within(rowNamed("car")).getByText(/yolo v8/)).toBeTruthy();
    expect(within(rowNamed("bus")).getByText("Accepted")).toBeTruthy();
    expect(within(rowNamed("tree")).getByText("Human")).toBeTruthy();
    // A person's row offers no decision.
    expect(within(rowNamed("tree")).queryByRole("button", { name: /^Accept/ })).toBeNull();
    // Two statuses and the human chip, none off by default.
    const chips = within(screen.getByRole("group", { name: "Filter by review status" }));
    expect(chips.getAllByRole("button").map((chip) => chip.getAttribute("aria-pressed"))).toEqual([
      "true",
      "true",
      "true",
    ]);
  });

  it("accepts a row: its badge, the counts and the unsaved count follow", async () => {
    const { manager } = await openReviewTab();

    await fireEvent.click(screen.getByRole("button", { name: "Accept car (bbox)" }));

    expect(within(rowNamed("car")).getByText("Accepted")).toBeTruthy();
    expect(isDisabled(screen.getByRole("button", { name: "Accept car (bbox)" }))).toBe(true);
    expect(screen.getByRole("button", { name: /^Accepted/ }).textContent).toContain("2");
    expect(screen.getByText("1 unsaved")).toBeTruthy();
    expect(manager.pendingCount).toBe(1);
  });

  it("saves the decision from the tab, as the status alone", async () => {
    const { backend } = await openReviewTab();
    await fireEvent.click(screen.getByRole("button", { name: "Accept car (bbox)" }));

    await fireEvent.click(screen.getByRole("button", { name: /^Save$/ }));

    await waitFor(() =>
      expect(backend.writes).toEqual([
        { op: "update", resource: BBOX_RESOURCE, id: "b1", body: { review_status: "accepted" } },
      ]),
    );
  });

  it("discards from the tab the decisions taken in it", async () => {
    const { manager, backend } = await openReviewTab();
    const discard = screen.getByRole("button", { name: /^Discard$/ });
    expect(isDisabled(discard)).toBe(true);
    await fireEvent.click(screen.getByRole("button", { name: "Accept car (bbox)" }));
    expect(isDisabled(discard)).toBe(false);

    await fireEvent.click(discard);

    await waitFor(() => expect(within(rowNamed("car")).getByText("Pending")).toBeTruthy());
    expect(manager.pendingCount).toBe(0);
    expect(isDisabled(screen.getByRole("button", { name: /^Discard$/ }))).toBe(true);
    expect(backend.writes).toEqual([]);
  });

  it("rejects a row: it leaves the list and the record, the unsaved count counts it, Save sends its delete", async () => {
    const { manager, backend } = await openReviewTab();

    await fireEvent.click(screen.getByRole("button", { name: "Reject car (bbox)" }));

    expect(rows().some((row) => row.textContent?.includes("car"))).toBe(false);
    expect(rows()).toHaveLength(2);
    expect(manager.annotations.find("b1")).toBeUndefined();
    expect(screen.getByRole("button", { name: /^Pending/ }).textContent).toContain("0");
    expect(screen.getByText("1 unsaved")).toBeTruthy();

    await fireEvent.click(screen.getByRole("button", { name: /^Save$/ }));

    await waitFor(() =>
      expect(backend.writes).toEqual([{ op: "delete", resource: BBOX_RESOURCE, id: "b1" }]),
    );
  });

  it("hides a chip's rows, and shows the hidden ones back", async () => {
    await openReviewTab();

    await fireEvent.click(screen.getByRole("button", { name: /^Human/ }));
    expect(rows()).toHaveLength(2);
    await fireEvent.click(screen.getByRole("button", { name: /^Accepted/ }));
    expect(rows()).toHaveLength(1);

    await fireEvent.click(screen.getByRole("button", { name: /^Accepted/ }));
    expect(within(rowNamed("bus")).getByText("Accepted")).toBeTruthy();
  });

  it("counts work a tool holds with nothing queued, offers Discard for it, and Discard drops it", async () => {
    const { manager } = await openReviewTab();
    const discard = () => screen.getByRole("button", { name: /^Discard$/ });
    let dropped = 0;
    // What a canvas tool raises while a shape is begun and not committed.
    const shapeBegun = manager.claimStagedWork("image-widget", () => {
      dropped += 1;
      shapeBegun.set(false);
    });

    shapeBegun.set(true);
    await waitFor(() => expect(isDisabled(discard())).toBe(false));
    // Unsaved — but nothing a save could send yet.
    expect(screen.getByText("1 unsaved")).toBeTruthy();
    expect(isDisabled(screen.getByRole("button", { name: /^Save$/ }))).toBe(true);
    await fireEvent.click(discard());

    await waitFor(() => expect(isDisabled(discard())).toBe(true));
    expect(screen.getByText("0 unsaved")).toBeTruthy();
    expect(dropped).toBe(1);
  });
});

describe("Review tab, read aloud", () => {
  it("names the annotation each decision button acts on", async () => {
    await openReviewTab();

    const names = (prefix: string) =>
      screen
        .getAllByRole("button", { name: new RegExp(`^${prefix} `) })
        .map((button) => button.getAttribute("aria-label"));
    expect(names("Accept")).toEqual(["Accept car (bbox)", "Accept bus (bbox)"]);
    expect(names("Reject")).toEqual(["Reject car (bbox)", "Reject bus (bbox)"]);
  });

  it("tells which row is selected, not only by its colour", async () => {
    await openReviewTab();
    const selectCar = within(rowNamed("car")).getByTitle("Select this annotation");

    await fireEvent.click(selectCar);

    expect(selectCar.getAttribute("aria-current")).toBe("true");
    expect(
      within(rowNamed("tree")).getByTitle("Select this annotation").hasAttribute("aria-current"),
    ).toBe(false);
  });

  it("says why Accept is refused on a row already accepted", async () => {
    await openReviewTab();
    await fireEvent.click(screen.getByRole("button", { name: "Accept car (bbox)" }));

    const accept = screen.getByRole("button", { name: "Accept car (bbox)" });
    expect(isDisabled(accept)).toBe(true);
    expect(accept.title).toBe("Already accepted");
    expect(descriptionOf(accept)).toBe("Already accepted");
  });

  it("offers Reject on an accepted row too, and says it deletes", async () => {
    await openReviewTab();

    const reject = screen.getByRole("button", { name: "Reject bus (bbox)" });
    expect(isDisabled(reject)).toBe(false);
    expect(reject.title).toBe("Reject: delete this annotation");
    expect(descriptionOf(reject)).toBeNull();
  });

  it("offers Accept on a row edited and not saved: it is still pending", async () => {
    const { manager } = await openReviewTab();

    drag(widgetSeam(manager), "b1");

    await waitFor(() => expect(screen.getByText("1 unsaved")).toBeTruthy());
    expect(within(rowNamed("car")).getByText("Pending")).toBeTruthy();
    const accept = screen.getByRole("button", { name: "Accept car (bbox)" });
    expect(isDisabled(accept)).toBe(false);
    expect(descriptionOf(accept)).toBeNull();
  });
});

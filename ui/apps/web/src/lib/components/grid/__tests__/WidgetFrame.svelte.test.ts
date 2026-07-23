/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { cleanup, render } from "@testing-library/svelte";
import { tick } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

import WidgetFrame from "../WidgetFrame.svelte";
import ThrowingWidget from "./ThrowingWidget.svelte";
import type { WidgetExtensionConfig, WidgetInstance } from "$lib/extensions/types.js";

afterEach(() => cleanup());

describe("WidgetFrame — error boundary", () => {
  it("shows a fallback on widget crash and recovers through reset", async () => {
    const crash = { value: true };
    const widget: WidgetInstance = {
      id: "w1",
      extensionName: "throwing",
      title: "Flaky widget",
      layout: { x: 0, y: 0, w: 6, h: 6 },
      options: { crash },
    };
    const config = {
      name: "throwing",
      label: "Throwing",
      icon: "square",
      defaultLayout: { x: 0, y: 0, w: 6, h: 6 },
      component: ThrowingWidget,
    } as unknown as WidgetExtensionConfig;

    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      const { container, getByText } = render(WidgetFrame, {
        props: { widget, config, onRemove: () => {} },
      });
      await tick();

      // The crash is contained: fallback + error message shown, frame (title
      // bar) still alive, and the error was reported with the widget's name.
      expect(container.querySelectorAll("[data-testid='widget-alive']")).toHaveLength(0);
      expect(getByText("This widget crashed.")).toBeTruthy();
      expect(getByText("widget exploded")).toBeTruthy();
      expect(getByText("Flaky widget")).toBeTruthy();
      expect(
        consoleError.mock.calls.some((args) =>
          String(args[0]).includes('Widget "Flaky widget" crashed'),
        ),
      ).toBe(true);

      // reset() re-creates the widget content; with the crash flag cleared the
      // widget renders normally again.
      crash.value = false;
      getByText("Reload widget").click();
      await tick();
      expect(container.querySelectorAll("[data-testid='widget-alive']")).toHaveLength(1);
      expect(container.querySelectorAll("button").length).toBeGreaterThan(0); // frame close button still there
    } finally {
      consoleError.mockRestore();
    }
  });
});

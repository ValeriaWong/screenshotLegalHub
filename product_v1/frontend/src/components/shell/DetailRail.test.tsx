import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { afterEach, describe, it, expect } from "vitest";
import { DetailRail, DetailRailProvider, useDetailRail } from "./DetailRail";
import { I18nProvider, zh, en } from "../../i18n";
import { SourceViewer } from "../../features/source-navigation/SourceViewer";
import { Feedback } from "../feedback";
afterEach(cleanup);
function Controls() {
  const rail = useDetailRail();
  return (
    <>
      <button
        onClick={() =>
          rail.open({
            type: "source",
            source: {
              id: "r",
              evidence_id: "e",
              evidence_page: 1,
              raw_coordinate_space: "pixels",
              quote: "",
            },
            viewer: {
              type: "image",
              url: "/demo.png",
              filename: "first.png",
              bbox: [10, 20, 50, 80],
              width: 100,
              height: 100,
            },
          })
        }
      >
        first
      </button>
      <button
        onClick={() =>
          rail.open({
            type: "fact",
            entity: {
              id: "f",
              kind: "fact",
              title: "Fact detail",
              case_id: "c",
              analysis_run_id: "r",
              skill_run_id: "s",
              status: "unknown",
              review_status: "unreviewed",
              source_refs: [],
              details: {},
              output_digest: "d",
            },
          })
        }
      >
        second
      </button>
    </>
  );
}
describe("shared rail and source viewer", () => {
  it("switches content, collapses, resizes and closes", () => {
    render(
      <I18nProvider>
        <DetailRailProvider>
          <Controls />
          <DetailRail />
        </DetailRailProvider>
      </I18nProvider>,
    );
    fireEvent.click(screen.getByText("first"));
    expect(screen.getByTestId("source-bbox")).toHaveStyle({
      left: "10%",
      top: "20%",
      width: "40%",
      height: "60%",
    });
    fireEvent.change(screen.getByRole("slider"), { target: { value: "550" } });
    expect(localStorage.getItem("railWidth")).toBe("550");
    fireEvent.click(screen.getByLabelText("折叠"));
    expect(screen.queryByTestId("source-bbox")).not.toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("展开"));
    fireEvent.click(screen.getByText("second"));
    expect(
      screen.getByRole("heading", { name: "Fact detail" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("关闭"));
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
  });
  it("shows full source without bbox and explicit failure state", () => {
    render(
      <I18nProvider>
        <SourceViewer
          content={{
            type: "image",
            url: "/missing.png",
            filename: "missing.png",
            regions: [],
          }}
        />
      </I18nProvider>,
    );
    expect(screen.getByText("未提供坐标，显示完整来源")).toBeInTheDocument();
    fireEvent.error(screen.getByRole("img"));
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
  it("provides loading, empty, not-run and error feedback", () => {
    for (const state of ["loading", "empty", "notRun", "error"] as const) {
      const view = render(
        <I18nProvider>
          <Feedback state={state} />
        </I18nProvider>,
      );
      expect(
        screen.getByRole(state === "error" ? "alert" : "status"),
      ).toBeInTheDocument();
      view.unmount();
    }
  });
  it("has matching translated UI keys", () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(zh).sort());
    expect(Object.values(en).every(Boolean)).toBe(true);
  });
});

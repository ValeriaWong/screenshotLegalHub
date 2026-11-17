import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { I18nProvider } from "../../i18n";
import type { SourceRef, EvidenceItem } from "../../api/client";
import { SourceViewer } from "./SourceViewer";
import { viewerFor } from "./index";

afterEach(() => cleanup());
const region = (id: string, bbox: [number, number, number, number], evidence_id = "image"): SourceRef =>
  ({ id, evidence_id, bbox, quote: "", raw_coordinate_space: "pixels" });
const content = { type: "image" as const, url: "/image", filename: "image.png", width: 100, height: 200,
  regions: [region("region.render.message_row.one", [10, 20, 60, 80]), region("region.annotation.avator.two", [20, 100, 40, 130])] };
function view(value = content) {
  localStorage.setItem("locale", "zh-CN");
  return render(<I18nProvider><SourceViewer content={value} /></I18nProvider>);
}
it("shows existing image regions without requiring a selected citation", () => {
  view();
  expect(screen.getAllByTestId("source-bbox")).toHaveLength(2);
  expect(screen.queryByText("未提供坐标，显示完整来源")).not.toBeInTheDocument();
  fireEvent.change(screen.getByRole("combobox"), { target: { value: content.regions[1].id } });
  expect(screen.getAllByTestId("source-bbox")).toHaveLength(1);
  expect(screen.getByText(/\[20, 100, 40, 130\]/)).toBeInTheDocument();
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "none" } });
  expect(screen.queryByTestId("source-bbox")).not.toBeInTheDocument();
});
it("preserves citation highlighting and allows all regions to be inspected", () => {
  localStorage.setItem("locale", "zh-CN");
  render(<I18nProvider><SourceViewer content={{ ...content, bbox: [10, 20, 60, 80], highlightText: "Quoted message" }} /></I18nProvider>);
  expect(screen.getAllByTestId("source-bbox")).toHaveLength(1);
  expect(screen.getByText("Quoted message")).toBeInTheDocument();
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "all" } });
  expect(screen.getAllByTestId("source-bbox")).toHaveLength(2);
});
it("distinguishes an unloaded region list from a genuinely empty one", () => {
  localStorage.setItem("locale", "zh-CN");
  const result = render(<I18nProvider><SourceViewer content={{ ...content, regions: undefined }} /></I18nProvider>);
  expect(screen.getByText(/区域列表尚未加载/)).toBeInTheDocument();
  result.rerender(<I18nProvider><SourceViewer content={{ ...content, regions: [] }} /></I18nProvider>);
  expect(screen.getByText("未提供坐标，显示完整来源")).toBeInTheDocument();
});
it("only carries regions belonging to the requested evidence", () => {
  const evidence: EvidenceItem = { id: "image", case_id: "case", filename: "image.png", mime_type: "image/png", sha256: "hash", storage_path: "case/image.png", size_bytes: 10, kind: "image", width: 100, height: 200 };
  const result = viewerFor("case", evidence, undefined, [...content.regions, region("other", [0, 0, 1, 1], "other-image")]);
  expect(result.regions).toHaveLength(2);
});

it("uses normalized document coordinates independently of image pixel size", () => {
  render(<I18nProvider><SourceViewer content={{type:"image",url:"/document/page",filename:"document",width:2000,height:3000,bbox:[100,200,500,600],coordinateSpace:"normalized_1000",originalUrl:"/original.pdf"}} /></I18nProvider>);
  expect(screen.getByTestId("source-bbox")).toHaveStyle({left:"10%",top:"20%",width:"40%",height:"40%"});
  expect(screen.getByRole("link", {name:"打开原文件"})).toHaveAttribute("href","/original.pdf");
});

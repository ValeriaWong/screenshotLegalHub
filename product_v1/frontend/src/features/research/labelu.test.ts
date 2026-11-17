import { it,expect } from "vitest";
import { exportLabelU,importLabelU } from "./labelu";
const image={sha256:"original-sha",width:200,height:160};
it("roundtrips LabelU xywh into original-pixel xyxy without scaling twice",()=>{
  const data=exportLabelU(image,[10,20,120,80],"问题","答案","message");
  expect(data.annotations[0]).toMatchObject({x:10,y:20,width:110,height:60});
  expect(importLabelU(data,image)).toEqual({bbox:[10,20,120,80],question:"问题",target:"答案"});
});
it("rejects mismatched originals, invalid geometry and ambiguous multi-region imports",()=>{
  const data=exportLabelU(image,[10,20,120,80],"问题","答案","message");
  expect(()=>importLabelU(data,{...image,sha256:"other"})).toThrow(/不匹配/);
  expect(()=>importLabelU({...data,annotations:[{...data.annotations[0],width:1000}]},image)).toThrow(/矩形/);
  expect(()=>importLabelU({...data,annotations:[...data.annotations,...data.annotations]},image)).toThrow(/一个参考框/);
});

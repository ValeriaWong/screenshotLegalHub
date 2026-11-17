import asyncio,json,sys
from pathlib import Path
r=Path(r'D:/workspace/screenshotLegalHub');sys.path.insert(0,str(r/'product_v1/backend/src'));from screenshotlegal.method_reproductions.paper_bridge import execute
async def no_call(*a):raise AssertionError('planning cannot call a model')
async def main():
 request=json.loads((r/'paper/author_reproductions/graphrag/native_input.json').read_text(encoding='utf-8'));request['mode']='plan_native';result=await execute('graphrag',request,no_call);(r/'paper/author_reproductions/graphrag/native_plan.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='context'}))
asyncio.run(main())

"""Execute named method modules; no method implementation branches live here."""
from .catalog import METHOD_MODULES,method_metadata,method_module
from .context import MethodContext

async def run_method(method,visible,sources,call,tool,system,demo_output,options,raw_call=None,author_record=None):
    module=method_module(method)
    if module.IMPLEMENTATION_STATUS!='implemented':
        raise ValueError('方法仅已登记，尚未实现，不可创建运行：'+module.METHOD_NAME)
    context=MethodContext(visible,sources,call,tool,system,demo_output,options,raw_call,author_record)
    return await module.run(context)

__all__=['METHOD_MODULES','method_metadata','method_module','run_method']

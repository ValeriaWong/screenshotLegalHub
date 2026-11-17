"""Load pinned MetaGPT software SOP unchanged, with remote transport and disabled optional resources.
Only eager package exports/imports are bypassed. Active Team/Environment/Role/Memory,
software actions, parsers and prompts execute author source. Long-term memory is off;
its classes are loaded but local index/embedding operations fail explicitly if invoked.
"""
import asyncio,importlib,inspect,json,os,pickle,sys,types,typing
from pathlib import Path
from author_runtime import source,original_definitions,call,tool


def load(runtime):
    folder,provenance=source('metagpt')
    runtime=Path(runtime).resolve();runtime.mkdir(parents=True,exist_ok=True)
    (runtime/'.project_root').touch();(runtime/'config').mkdir(exist_ok=True)
    import yaml
    settings=yaml.safe_load((folder/'config/config.yaml').read_text(encoding='utf-8'))
    settings.update(OPENAI_API_KEY='unused-parent-transport',OPENAI_API_BASE='http://127.0.0.1:1/v1',LONG_TERM_MEMORY=False,PROMPT_FORMAT='json',SEARCH_ENGINE='custom')
    (runtime/'config/config.yaml').write_text(yaml.safe_dump(settings),encoding='utf-8')
    # Observed Windows locale writes produced non-UTF8 Python source; use UTF8 text output.
    original_text_write=Path.write_text
    def utf8_text_write(path,data,encoding=None,errors=None,newline=None):
        return original_text_write(path,data,encoding=encoding or 'utf-8',errors=errors,newline=newline)
    Path.write_text=utf8_text_write
    os.chdir(runtime)
    for name,relative in [('metagpt','metagpt'),('metagpt.actions','metagpt/actions'),('metagpt.roles','metagpt/roles'),('metagpt.memory','metagpt/memory'),('metagpt.document_store','metagpt/document_store'),('metagpt.utils','metagpt/utils')]:
        module=types.ModuleType(name);module.__path__=[str(folder/relative)];sys.modules[name]=module
    counter=0
    transport_lock=asyncio.Lock()
    class Transport:
        async def aask(self,prompt,system_msgs=None,**kwargs):
            nonlocal counter
            label='role'
            frame=inspect.currentframe().f_back
            while frame:
                obj=frame.f_locals.get('self')
                if obj is not None and isinstance(obj,actions.Action):
                    label=obj.__class__.__name__;break
                frame=frame.f_back
            messages=[dict(role='system',content=s) for s in (system_msgs or []) if s]
            messages.append(dict(role='user',content=prompt))
            stage=label+'.'+str(counter);counter+=1
            async with transport_lock:
                return await asyncio.to_thread(call,stage,messages,dict(model='gpt-4',temperature=0.,max_tokens=6144))
    llm=types.ModuleType('metagpt.llm');llm.LLM=Transport
    class HumanProvider:
        def __init__(self,*args,**kwargs):raise ValueError('Human-provider path is outside the authorized automatic run')
    llm.HumanProvider=HumanProvider;sys.modules['metagpt.llm']=llm
    import metagpt.const as const
    import metagpt.config as config
    import metagpt.logs as logs
    # Source config is used; no supplier credential enters it. Parent tracks actual fees/cap.
    if config.CONFIG.long_term_memory:raise ValueError('Local vector memory is deferred')
    actions=sys.modules['metagpt.actions'];roles=sys.modules['metagpt.roles'];memory=sys.modules['metagpt.memory']
    actions.ActionOutput=importlib.import_module('metagpt.actions.action_output').ActionOutput
    action=importlib.import_module('metagpt.actions.action');actions.Action=action.Action
    action.Action._aask_v1=inspect.unwrap(action.Action._aask_v1)
    actions.BossRequirement=importlib.import_module('metagpt.actions.add_requirement').BossRequirement
    from metagpt.schema import Message
    from metagpt.tools import SearchEngineType
    # SkSearchEngine is unused in startup; load the complete original SearchEngine class only.
    search=types.ModuleType('metagpt.tools.search_engine');sys.modules[search.__name__]=search
    search.__dict__.update(typing.__dict__,CONFIG=config.CONFIG,SearchEngineType=SearchEngineType,importlib=importlib,__name__=search.__name__)
    original_definitions(folder/'metagpt/tools/search_engine.py',['SearchEngine'],search.__dict__)
    actions.WritePRD=importlib.import_module('metagpt.actions.write_prd').WritePRD
    # Mermaid's text output is preserved; graphics rendering isn't needed for algorithm execution.
    mermaid=importlib.import_module('metagpt.utils.mermaid')
    async def diagram(text,path,**kwargs):
        path=Path(str(path)+'.mmd').resolve()
        if not path.is_relative_to(runtime):raise ValueError('Diagram output escapes isolated run')
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')
        tool('metagpt.diagram_source',dict(path=str(path.relative_to(runtime)),text=text,graphics_rendered=False))
        return -1
    mermaid.mermaid_to_file=diagram
    actions.WriteDesign=importlib.import_module('metagpt.actions.design_api').WriteDesign
    actions.WriteTasks=importlib.import_module('metagpt.actions.project_management').WriteTasks
    for name,file in [('WriteCode','write_code'),('WriteCodeReview','write_code_review')]:
        cls=getattr(importlib.import_module('metagpt.actions.'+file),name)
        cls.write_code=inspect.unwrap(cls.write_code)
        setattr(actions,name,cls)
    memory.Memory=importlib.import_module('metagpt.memory.memory').Memory
    # Preserve all optional-memory class bodies; guard unexecuted resource operations.
    class DeferredResource:
        def __init__(self,*args,**kwargs):raise ValueError('Local indexing/embedding resource path is deferred')
        def __getattr__(self,name):raise ValueError('Local indexing/embedding resource path is deferred')
    class DeferredModule:
        def __getattr__(self,name):raise ValueError('Local indexing/embedding resource path is deferred')
    base=importlib.import_module('metagpt.document_store.base_store')
    fs=types.ModuleType('metagpt.document_store.faiss_store');sys.modules[fs.__name__]=fs
    fs.__dict__.update(__name__=fs.__name__,LocalStore=base.LocalStore,Path=Path,Optional=typing.Optional,pickle=pickle,
        faiss=DeferredModule(),FAISS=DeferredResource,OpenAIEmbeddings=DeferredResource,Document=DeferredResource,logger=logs.logger)
    original_definitions(folder/'metagpt/document_store/faiss_store.py',['FaissStore'],fs.__dict__)
    serialize=importlib.import_module('metagpt.utils.serialize')
    ms=types.ModuleType('metagpt.memory.memory_storage');sys.modules[ms.__name__]=ms
    ms.__dict__.update(__name__=ms.__name__,FaissStore=fs.FaissStore,List=typing.List,Path=Path,MEM_TTL=const.MEM_TTL,
        DATA_PATH=const.DATA_PATH,logger=logs.logger,Message=Message,FAISS=DeferredResource,
        serialize_message=serialize.serialize_message,deserialize_message=serialize.deserialize_message)
    original_definitions(folder/'metagpt/memory/memory_storage.py',['MemoryStorage'],ms.__dict__)
    memory.LongTermMemory=importlib.import_module('metagpt.memory.longterm_memory').LongTermMemory
    roles.Role=importlib.import_module('metagpt.roles.role').Role
    for name,file in [('ProductManager','product_manager'),('Architect','architect'),('ProjectManager','project_manager'),('Engineer','engineer')]:
        setattr(roles,name,getattr(importlib.import_module('metagpt.roles.'+file),name))
    from metagpt.environment import Environment
    from metagpt.roles.role import RoleContext
    RoleContext.update_forward_refs(Environment=Environment)
    from metagpt.team import Team
    published=Environment.publish_message
    def publish(self,message):
        published(self,message)
        tool('metagpt.published_message',dict(role=message.role,content=message.content,
            cause_by=getattr(message.cause_by,'__name__',str(message.cause_by)),
            sent_from=str(getattr(message.sent_from,'profile',message.sent_from)),send_to=str(getattr(message.send_to,'profile',message.send_to)),
            structured=message.instruct_content.dict() if message.instruct_content else None))
    Environment.publish_message=publish
    # Author uses model-provided paths in recursive deletes. Restrict to a new run workspace;
    # refuse overwrites entirely, so no existing run or business file is recursively deleted.
    class IsolatedShutil:
        @staticmethod
        def rmtree(path,*args,**kwargs):
            p=Path(path).resolve()
            if not p.is_relative_to(runtime/'workspace') or p==runtime/'workspace':raise ValueError('Author delete path escapes isolated generated workspace')
            if p.exists():raise FileExistsError('Existing generated output is preserved; choose a fresh run')
            raise FileNotFoundError(p)
    import metagpt.actions.design_api as design
    import metagpt.roles.engineer as engineering
    design.shutil=IsolatedShutil;engineering.shutil=IsolatedShutil
    original_write=engineering.Engineer.write_file
    def write_file(self,filename,code):
        # Each new filename enters once from the model; author writes unchanged thereafter.
        target=(self.get_workspace()/filename).resolve()
        if not target.is_relative_to(runtime/'workspace'):raise ValueError('Generated filename escapes isolated workspace')
        return original_write(self,filename,code)
    engineering.Engineer.write_file=write_file
    loaded=dict(folder=folder,provenance=provenance,Team=Team,roles=roles,Action=action.Action,ActionOutput=actions.ActionOutput,
        Message=Message,config=config.CONFIG,calls=lambda:counter)
    loaded['adaptations']=['remote LLM transport; original prompts/parsers retained','paid retry decorators omitted, function bodies unchanged',
        'unused eager package exports omitted','default long-term memory remains off; original optional classes loaded with fail-on-use resource guards',
        'Mermaid source retained; graphics rendering deferred','Windows text output defaults to UTF-8 to produce importable Python source','original destructive output recreation refuses existing paths and paths outside isolated workspace',
        'author-supported JSON prompt format; startup search was already commented out; custom no-search engine avoids unused provider setup']
    return loaded

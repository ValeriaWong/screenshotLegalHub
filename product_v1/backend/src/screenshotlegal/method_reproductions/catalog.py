"""Stable method names and one-module-per-method dispatch metadata."""
from importlib import import_module

METHOD_MODULES = {'E00': 'e00_single_shot', 'E01': 'e01_react', 'E02': 'e02_staged_without_matterpack', 'E03': 'e03_staged_with_matterpack', 'E04': 'e04_symbolic_verifier', 'E05': 'e05_self_refine', 'E06': 'e06_legalreasoner_verifier', 'E07': 'e07_agentscourt_adversarial', 'E08': 'e08_agentscourt_judge', 'E09': 'e09_l_mad', 'E10': 'e10_factor_guided_retrieval', 'E11': 'e11_legal_r1', 'E12': 'e12_crag', 'E13': 'e13_graphreader', 'E14': 'e14_chain_of_agents', 'E15': 'e15_raptor', 'E16': 'e16_lightrag', 'E17': 'e17_lawflow_review', 'E18': 'e18_jurisma', 'E19': 'e19_scale', 'E20': 'e20_verdict', 'E21': 'e21_reflexion', 'E22': 'e22_metagpt', 'E23': 'b01_legalagentbench', 'E24': 'r04_graphrag', 'E25': 'l06_legal_reasoning_paths'}

def method_module(method_id):
    try:name=METHOD_MODULES[method_id]
    except KeyError:raise KeyError('方法不存在') from None
    return import_module(__package__+'.'+name)

def method_metadata(method_id):
    module=method_module(method_id)
    return dict(reproduction_name=module.METHOD_NAME,
                implementation_module=module.__name__,
                implementation_file='product_v1/backend/src/screenshotlegal/method_reproductions/'+module.METHOD_NAME+'.py',
                implementation_status=module.IMPLEMENTATION_STATUS,
                reproduction_level=module.REPRODUCTION_LEVEL,
                reproduction_scope=module.REPRODUCTION_SCOPE,
                paper_sources=module.PAPER_REFERENCES,
                original_paper_reproduced=module.ADAPTATION_AUDIT['original_paper_reproduced'],
                author_code_status=module.ADAPTATION_AUDIT['author_code_execution'],
                adaptation_assessment=module.ADAPTATION_AUDIT,
                original_paper_contracts=module.ORIGINAL_PAPER_CONTRACTS)

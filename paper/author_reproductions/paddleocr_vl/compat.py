"""Explicit API keyword shim for the pinned author's unmodified model source.

The author calls create_causal_mask(inputs_embeds=...), while the pinned
Transformers API names that parameter input_embeds. Only the keyword is renamed;
the original Transformers mask function computes the mask without alteration.
"""
import inspect

def install_causal_mask_alias(module):
    original=module.create_causal_mask
    parameters=inspect.signature(original).parameters
    if 'input_embeds' not in parameters or 'inputs_embeds' in parameters:
        return dict(applied=False,reason='No keyword mismatch')
    def compatible(*args,**kwargs):
        if 'inputs_embeds' in kwargs:
            if 'input_embeds' in kwargs:raise TypeError('Both embedding keyword forms supplied')
            kwargs['input_embeds']=kwargs.pop('inputs_embeds')
        return original(*args,**kwargs)
    module.create_causal_mask=compatible
    return dict(applied=True,rule='inputs_embeds -> input_embeds',original_signature=str(inspect.signature(original)),algorithm_changed=False)

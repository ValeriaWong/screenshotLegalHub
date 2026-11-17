"""The author typo adapter preserves inputs and invokes the unchanged mask function."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest
spec=importlib.util.spec_from_file_location('paddle_compat',Path(__file__).resolve().parents[3]/'paper/author_reproductions/paddleocr_vl/compat.py');compat=importlib.util.module_from_spec(spec);spec.loader.exec_module(compat)
def test_only_embedding_keyword_is_renamed():
    calls=[];embedding=object();mask=object();cache=object()
    def original(*,config,input_embeds,attention_mask,cache_position):
        calls.append((config,input_embeds,attention_mask,cache_position));return mask
    module=SimpleNamespace(create_causal_mask=original);info=compat.install_causal_mask_alias(module)
    assert info['applied'] and not info['algorithm_changed']
    assert module.create_causal_mask(config='c',inputs_embeds=embedding,attention_mask=mask,cache_position=cache) is mask
    assert calls==[('c',embedding,mask,cache)]
    with pytest.raises(TypeError):module.create_causal_mask(config='c',inputs_embeds=embedding,input_embeds=embedding,attention_mask=mask,cache_position=cache)

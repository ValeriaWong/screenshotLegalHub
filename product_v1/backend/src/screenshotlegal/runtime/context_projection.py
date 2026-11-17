import copy

def project(needs, state):
    """Only declared selectors cross a node boundary; no prompts or raw responses."""
    missing=set(needs)-state.keys()
    if missing:
        raise ValueError('Missing context selectors: '+','.join(sorted(missing)))
    return {key:copy.deepcopy(state[key]) for key in needs}

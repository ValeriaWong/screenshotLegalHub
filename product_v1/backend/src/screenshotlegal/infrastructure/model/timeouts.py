"""Explicit transport inactivity limits and optional total budget, frozen per model."""
import httpx

def policy(seconds=90,total=None):
    return dict(connect=seconds,read=seconds,write=seconds,pool=seconds,total=total)

def transport(value):
    return httpx.Timeout(connect=value['connect'],read=value['read'],write=value['write'],pool=value['pool'])

def phase(error):
    for cls,name in [(httpx.ConnectTimeout,'connect'),(httpx.ReadTimeout,'read'),(httpx.WriteTimeout,'write'),(httpx.PoolTimeout,'pool')]:
        if isinstance(error,cls):return name
    return 'total' if isinstance(error,TimeoutError) else 'transport'

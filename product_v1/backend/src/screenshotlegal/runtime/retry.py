import asyncio
import time

async def with_retry(operation, policy, on_attempt):
    for attempt in range(1,policy.max_attempts+1):
        start=time.perf_counter()
        try:
            output=await operation()
        except Exception as error:
            await on_attempt(attempt,None,error,time.perf_counter()-start)
            if type(error).__name__ not in policy.retryable_errors or attempt==policy.max_attempts:
                raise
            await asyncio.sleep(policy.backoff * 2**(attempt-1))
        else:
            await on_attempt(attempt,output,None,time.perf_counter()-start)
            return output

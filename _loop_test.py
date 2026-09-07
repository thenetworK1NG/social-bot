import datetime as dt
from run import ActivityLoop

loop = ActivityLoop()
# Simulate: we're in the middle of a long wait, background activity should fire
loop.next_post_at = dt.datetime.now() + dt.timedelta(hours=2)
loop.last_engage = dt.datetime.now() - dt.timedelta(minutes=10)
print("Step 1 (due background engagement)")
loop.run_step()
print("Step 2 (not due yet - should mostly idle)")
loop.run_step()
print("OK - background activity loop ran without errors")

import datetime
from datetime import timezone, timedelta

local_now = datetime.datetime.now()
cot_now = datetime.datetime.now(timezone(timedelta(hours=-5)))

print("Local now:", local_now)
print("Local weekday:", local_now.weekday())
print("COT now:", cot_now)
print("COT weekday:", cot_now.weekday())

import tacit
class Raw(tacit.Schema):
    amount: float
reveal_type(Raw.amount)
Raw.amnt
try:
    print(Raw.amount)
except Exception as e:
    print("runtime:", type(e).__name__, e)

from typing import reveal_type
from sqlalchemy import select, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase): ...

class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    amount: Mapped[float]
    status: Mapped[str] = mapped_column(String(10))

reveal_type(Order.amount)          # InstrumentedAttribute[float]
reveal_type(select(Order.amount))  # Select[tuple[float]]
select(Order.amnt)                 # typo -> static error
o = Order(id=1, amount="x", status="a")  # wrong type -> static error
reveal_type(o.amount)              # float
reveal_type(Order.amount > 3)
Order.status > 3  # accepted by checkers? 

import uvicorn
from typing import Annotated
from pydantic import BaseModel
from fastapi import FastAPI, Depends, Form
from contextlib import asynccontextmanager
from sqlalchemy import String, REAL, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import RedirectResponse

templates = Jinja2Templates(directory="templates")

app = FastAPI()
engine = create_async_engine("sqlite+aiosqlite:///expense_tracker.db")
new_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_session():
    async with new_session() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


class Base(DeclarativeBase):
    pass


class ExpenseModel(Base):
    __tablename__ = "expenses"
    id: Mapped[int] = mapped_column(primary_key=True)
    description: Mapped[str] = mapped_column(String)
    amount: Mapped[float] = mapped_column(REAL)
    date: Mapped[str] = mapped_column(String)


class Expense(BaseModel):
    description: str
    amount: float
    date: str


async def db_init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db_init()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
def root():
    return {"Msg": "Hello Expense Tracker!"}


@app.post(path="/expenses")
async def add_expense(expense: Expense, session: SessionDep):
    new_expense = ExpenseModel(**expense.dict())
    session.add(new_expense)
    await session.commit()
    await session.refresh(new_expense)

    return {
        "id": new_expense.id,
        "description": new_expense.description,
        "amount": new_expense.amount,
        "date": new_expense.date,
    }


@app.get(path="/expenses")
async def get_expenses(session: SessionDep):
    result = await session.execute(select(ExpenseModel))
    expenses = result.scalars().all()

    return [
        {"id": e.id, "description": e.description, "amount": e.amount, "date": e.date}
        for e in expenses
    ]

@app.get(path="/dashboard")
async def dashboard(request: Request, session: SessionDep):
    result = await session.execute(select(ExpenseModel))
    expenses = result.scalars().all()

    return templates.TemplateResponse(
        "index.html", {"request": request, "expenses": expenses}
    )


@app.post(path="/expenses_form")
async def expenses_form(
    description: str = Form(...),
    amount: float = Form(...),
    date: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    new_expense = ExpenseModel(description=description, amount=amount, date=date)
    session.add(new_expense)
    await session.commit()
    await session.refresh(new_expense)

    return RedirectResponse(url="/dashboard", status_code=303)

if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)

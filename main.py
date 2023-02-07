from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import ForeignKey, String, create_engine, select
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

"""
SQLAlchemyのモデル.

Based on:
* https://docs.sqlalchemy.org/en/20/orm/quickstart.html#declare-models
* https://fastapi.tiangolo.com/ja/tutorial/sql-databases/#create-the-database-models
"""


class Base(DeclarativeBase):
    """各DBモデルの基底クラス."""

    pass


class User(Base):
    """usersテーブルのDBモデル."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool]

    items: Mapped[list["Item"]] = relationship(back_populates="owner")


class Item(Base):
    """itemsテーブルのDBモデル."""

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(30), index=True)
    description: Mapped[str] = mapped_column(String(30), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    owner: Mapped["User"] = relationship(back_populates="items")


"""
Pydanticのモデル.

Based on:
* https://fastapi.tiangolo.com/ja/tutorial/sql-databases/#create-the-pydantic-models
"""


class ItemBase(BaseModel):
    """Itemの基底クラス."""

    title: str
    description: str | None = None


class ItemCreateRequest(ItemBase):
    """Item作成のリクエストを表現するクラス."""

    pass


class ItemResponse(ItemBase):
    """Itemのレスポンスを表現するクラス."""

    id: int
    owner_id: int

    class Config:
        orm_mode = True


class UserBase(BaseModel):
    """Userの基底クラス."""

    email: str


class UserCreateRequest(UserBase):
    """User作成のリクエストを表現するクラス."""

    password: str


class UserResponse(UserBase):
    """Userのレスポンスを表現するクラス."""

    id: int
    is_active: bool
    items: list[ItemResponse] = []

    class Config:
        orm_mode = True


"""
DBのCRUD操作を行う関数.

Based on:
* https://docs.sqlalchemy.org/en/20/changelog/migration_20.html#migration-orm-usage
* https://fastapi.tiangolo.com/ja/tutorial/sql-databases/#crud-utils
"""


def get_db_user(db: Session, user_id: int):
    """usersテーブルからuser_idに一致するUserを取得します."""
    return db.execute(select(User).where(User.id == user_id)).scalars().first()


def get_db_user_by_email(db: Session, email: str):
    """usersテーブルからemailに一致するUserを取得します."""
    return db.execute(select(User).where(User.email == email)).scalars().first()


def get_db_users(db: Session, skip: int = 0, limit: int = 100):
    """usersテーブルからUserをすべて取得します."""
    return db.execute(select(User).offset(skip).limit(limit)).scalars().all()


def create_db_user(db: Session, user: UserCreateRequest):
    """usersテーブルにUserを追加します."""
    fake_hashed_password = user.password + "notreallyhashed"
    db_user = User(
        email=user.email, hashed_password=fake_hashed_password, is_active=True
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_db_items(db: Session, skip: int = 0, limit: int = 100):
    """itemsテーブルからItemをすべて取得します."""
    return db.execute(select(Item).offset(skip).limit(limit)).scalars().all()


def create_db_user_item(db: Session, item: ItemCreateRequest, user_id: int):
    """itemsテーブルにItemを追加します."""
    db_item = Item(**item.dict(), owner_id=user_id)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


"""
FastAPIでSQLAlchemyを使うためのセットアップ.
"""
# DBセッションを作成するクラスを作る.
SQLALCHEMY_DATABASE_URL = "mysql+mysqldb://user:password@db/test"

# デバッグ用にecho=Trueに設定.
engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# DBマイグレーションを行う.
Base.metadata.create_all(bind=engine)

# FastAPIをインスタンス化.
app = FastAPI()


def get_db():
    """リクエストが来たらセッションを作成し、処理が完了したら閉じるためのDependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


"""
FastAPIのルーティング.
"""


@app.post("/users/", response_model=UserResponse)
def create_user(user: UserCreateRequest, db: Session = Depends(get_db)):
    """ユーザーを作成します."""
    db_user = get_db_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return create_db_user(db=db, user=user)


@app.get("/users/", response_model=list[UserResponse])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """ユーザーを一覧します."""
    users = get_db_users(db, skip=skip, limit=limit)
    return users


@app.get("/users/{user_id}", response_model=UserResponse)
def read_user(user_id: int, db: Session = Depends(get_db)):
    """ユーザーを取得します."""
    db_user = get_db_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@app.post("/users/{user_id}/items/", response_model=ItemResponse)
def create_item_for_user(
    user_id: int, item: ItemCreateRequest, db: Session = Depends(get_db)
):
    """ユーザーのアイテムを作成します."""
    return create_db_user_item(db=db, item=item, user_id=user_id)


@app.get("/items/", response_model=list[ItemResponse])
def read_items(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """アイテムを一覧します."""
    items = get_db_items(db, skip=skip, limit=limit)
    return items

"""Authentication service functions for Kirana AI Agent."""
from typing import Optional
from sqlalchemy.orm import Session

from app.auth.schemas import AuthenticatedPrincipal
from app.db.database import get_db_context
from app.db.models import Store, User


def get_or_create_default_store(db: Session) -> Store:
    """Ensure at least one default store exists (Store #1)."""
    store = db.query(Store).filter(Store.id == 1).first()
    if not store:
        store = Store(
            id=1,
            name="Lakshmi Kirana & General Store",
            address="Shop #4, Main Market, MG Road, Bengaluru",
            gstin="29ABCDE1234F1Z5",
        )
        db.add(store)
        db.commit()
        db.refresh(store)
    return store


def authenticate_telegram_user(
    telegram_user_id: int,
    db: Optional[Session] = None,
) -> Optional[AuthenticatedPrincipal]:
    """Authenticate a Telegram user ID against the database `users` table.

    Returns AuthenticatedPrincipal if user is active and mapped to a valid store,
    or None if unauthorized.
    """
    if not telegram_user_id:
        return None

    def _auth(session: Session) -> Optional[AuthenticatedPrincipal]:
        get_or_create_default_store(session)
        user = session.query(User).filter(
            User.telegram_user_id == telegram_user_id,
            User.active == True,
        ).first()

        if not user:
            # Single-store developer convenience:
            # Auto-bootstrap if 0 users exist or bind default unbound user
            all_users = session.query(User).all()
            if len(all_users) == 0 or (len(all_users) == 1 and all_users[0].telegram_user_id is None):
                return bootstrap_store_and_user(
                    store_name="Lakshmi Kirana & General Store",
                    telegram_user_id=telegram_user_id,
                    user_name="Store Owner",
                    role="OWNER",
                    db=session,
                )
            return None

        return AuthenticatedPrincipal(
            user_id=user.id,
            store_id=user.store_id,
            role=user.role,
            telegram_user_id=user.telegram_user_id,
            name=user.name,
        )

    if db is None:
        with get_db_context() as session:
            return _auth(session)
    return _auth(db)



def bootstrap_store_and_user(
    store_name: str = "Lakshmi Kirana & General Store",
    telegram_user_id: Optional[int] = None,
    user_name: str = "Store Owner",
    role: str = "OWNER",
    db: Optional[Session] = None,
) -> AuthenticatedPrincipal:
    """Bootstrap a store and associated user operator (useful for setup & testing)."""

    def _bootstrap(session: Session) -> AuthenticatedPrincipal:
        store = session.query(Store).filter(Store.name == store_name).first()
        if not store:
            store = Store(
                name=store_name,
                address="Shop #4, Main Market, MG Road, Bengaluru",
                gstin="29ABCDE1234F1Z5",
            )
            session.add(store)
            session.commit()
            session.refresh(store)


        user = None
        if telegram_user_id:
            user = session.query(User).filter(User.telegram_user_id == telegram_user_id).first()

        if not user:
            user = session.query(User).filter(User.store_id == store.id, User.name == user_name).first()

        if not user:
            user = User(
                store_id=store.id,
                telegram_user_id=telegram_user_id,
                name=user_name,
                role=role,
                active=True,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        elif telegram_user_id and user.telegram_user_id != telegram_user_id:
            user.telegram_user_id = telegram_user_id
            session.commit()
            session.refresh(user)

        return AuthenticatedPrincipal(
            user_id=user.id,
            store_id=user.store_id,
            role=user.role,
            telegram_user_id=user.telegram_user_id,
            name=user.name,
        )

    if db is None:
        with get_db_context() as session:
            return _bootstrap(session)
    return _bootstrap(db)


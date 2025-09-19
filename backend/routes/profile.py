# backend/routes/profile.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

from database import get_connection, get_user_profile, upsert_user_profile

router = APIRouter(prefix="/api/profile", tags=["Perfil"])

# --------- Schemas ---------
class ProfileOut(BaseModel):
    id: int = 1
    sender_name: Optional[str] = None
    sender_company: Optional[str] = None
    sender_email: Optional[EmailStr] = None
    sender_phone: Optional[str] = None
    sender_site: Optional[str] = None
    sender_signature: Optional[str] = None
    default_tone: Optional[str] = None
    default_language: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProfileIn(BaseModel):
    sender_name: Optional[str] = Field(default=None, description="Seu nome")
    sender_company: Optional[str] = Field(default=None, description="Nome da sua empresa")
    sender_email: Optional[EmailStr] = Field(default=None, description="Seu e-mail")
    sender_phone: Optional[str] = Field(default=None, description="Telefone/WhatsApp")
    sender_site: Optional[str] = Field(default=None, description="Site/Portfólio (opcional)")
    sender_signature: Optional[str] = Field(default=None, description="Assinatura padrão (rodapé)")
    default_tone: Optional[str] = Field(default=None, description="Tom padrão (ex.: 'profissional e próximo')")
    default_language: Optional[str] = Field(default=None, description="Idioma padrão (ex.: 'pt-PT')")


# --------- Endpoints ---------
@router.get("", response_model=ProfileOut)
def get_profile():
    """
    Retorna o perfil único (id=1).
    """
    with get_connection() as conn:
        data = get_user_profile(conn)
        if not data:
            raise HTTPException(status_code=500, detail="Perfil não encontrado.")
        return data


@router.put("", response_model=ProfileOut)
def update_profile(payload: ProfileIn):
    """
    Atualiza os campos enviados do perfil (id=1) e retorna o registro atualizado.
    """
    with get_connection() as conn:
        data = payload.model_dump(exclude_unset=True)
        updated = upsert_user_profile(conn, data)
        return updated

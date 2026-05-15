"""Endpoint bisnis."""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from db import repo

router = APIRouter(prefix="/businesses", tags=["businesses"])


class PayloadBisnis(BaseModel):
    """Data pendaftaran bisnis baru."""

    name: str
    owner_name: Optional[str] = None
    phone: Optional[str] = None
    business_type: str = Field(default="warung")


@router.get("")
def daftar_bisnis():
    """Menampilkan semua bisnis."""
    return {"items": repo.daftar_bisnis()}


@router.post("")
def buat_bisnis(payload: PayloadBisnis):
    """Mendaftarkan bisnis baru."""
    id_baru = repo.buat_bisnis_baru(
        nama=payload.name,
        nama_pemilik=payload.owner_name,
        telepon=payload.phone,
        tipe_bisnis=payload.business_type,
    )
    return {"id": id_baru, "message": "Bisnis berhasil dibuat"}

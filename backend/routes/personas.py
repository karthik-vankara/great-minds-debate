from fastapi import APIRouter, HTTPException

from backend.schemas import PersonaPayload, PersonaRecord
from personas import (
    BUILTIN_PERSONAS,
    get_active_personas,
    refresh_personas,
    remove_custom_persona,
    save_custom_persona,
)


router = APIRouter(prefix="/personas", tags=["personas"])


@router.get("", response_model=list[PersonaRecord])
def list_personas() -> list[PersonaRecord]:
    records: list[PersonaRecord] = []
    for key, data in get_active_personas().items():
        origin = "built-in" if key in BUILTIN_PERSONAS else "custom"
        records.append(PersonaRecord(key=key, origin=origin, data=PersonaPayload(**data)))
    return records


@router.post("/{key}", response_model=PersonaRecord)
def upsert_persona(key: str, payload: PersonaPayload) -> PersonaRecord:
    try:
        save_custom_persona(key, payload.model_dump())
        refresh_personas()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    data = get_active_personas().get(key)
    if not data:
        raise HTTPException(status_code=500, detail="Persona was not available after save.")

    return PersonaRecord(key=key, origin="custom", data=PersonaPayload(**data))


@router.delete("/{key}")
def delete_persona(key: str) -> dict[str, bool]:
    if key in BUILTIN_PERSONAS:
        raise HTTPException(status_code=400, detail="Built-in personas cannot be deleted.")

    deleted = remove_custom_persona(key)
    refresh_personas()
    if not deleted:
        raise HTTPException(status_code=404, detail="Persona not found.")

    return {"deleted": True}

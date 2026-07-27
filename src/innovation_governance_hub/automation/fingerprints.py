import hashlib


def fingerprint(kind: str, entity: str, entity_id: int) -> str:
    return hashlib.sha256(f"{kind}:{entity}:{entity_id}".encode()).hexdigest()

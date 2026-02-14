import hashlib

def row_hash(row: dict) -> str:
    canonical = "|".join(
        str(row[k]) for k in sorted(row.keys()) if k != "content_hash"
    )
    return hashlib.md5(canonical.encode("utf-8")).hexdigest()

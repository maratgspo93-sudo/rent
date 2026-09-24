"""Նկարների մշակում. վերակոդավորում JPEG-ի (ջնջում է EXIF-ը՝ այդ թվում GPS կոորդինատները) + dHash։
Առանց Pillow-ի նկարներ չենք ընդունում, որպեսզի EXIF-ով չբացահայտենք տանտիրոջ հասցեն։"""
import io

MAX_BYTES = 5 * 1024 * 1024

def sniff(data):
    if data[:3] == b"\xff\xd8\xff": return "jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n": return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP": return "webp"
    return None

def process_photo(data):
    """-> (jpeg_bytes, dhash_hex). ValueError՝ անթույլատրելի ֆայլի դեպքում։"""
    if len(data) > MAX_BYTES: raise ValueError("Նկարը 5 ՄԲ-ից մեծ է")
    if not sniff(data): raise ValueError("Թույլատրվում են միայն JPEG, PNG, WEBP")
    try:
        from PIL import Image
        import imagehash
    except ImportError:
        raise ValueError("Նկարների մշակումը միացված չէ (տեղադրեք Pillow և imagehash)")
    img = Image.open(io.BytesIO(data))
    img.load()
    img = img.convert("RGB")
    img.thumbnail((1600, 1600))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85)          # նոր ֆայլ՝ առանց EXIF-ի
    return out.getvalue(), str(imagehash.dhash(img))

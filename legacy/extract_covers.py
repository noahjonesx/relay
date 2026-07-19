import io, os
from mutagen.id3 import ID3, ID3NoHeaderError
from PIL import Image

MUSIC_DIR = r"C:\Users\noahx\Music\iPod"

extracted = 0
skipped = 0

for root, dirs, files in os.walk(MUSIC_DIR):
    mp3s = [f for f in files if f.endswith(".mp3")]
    if not mp3s:
        continue

    cover_path = os.path.join(root, "cover.jpg")

    for mp3 in mp3s:
        try:
            tags = ID3(os.path.join(root, mp3))
            for key in tags:
                if key.startswith("APIC"):
                    img_data = tags[key].data
                    img = Image.open(io.BytesIO(img_data)).convert("RGB")
                    img.save(cover_path, "JPEG", quality=90)
                    print(f"Extracted: {os.path.relpath(cover_path, MUSIC_DIR)}")
                    extracted += 1
                    break
            if os.path.exists(cover_path):
                break
        except (ID3NoHeaderError, Exception):
            continue

print(f"\nDone: {extracted} extracted")

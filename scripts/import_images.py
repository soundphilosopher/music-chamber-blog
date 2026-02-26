import curl_cffi
import time

from markdown.extensions.toc import slugify

images: dict[str, str] = {}

for title, url in images.items():
    # get unix timestamp
    timestamp = int(time.time())
    # download image with curl_cffi impersonating chrome
    response = curl_cffi.get(url, impersonate='chrome')
    # get image extension from content-type header
    extension = response.headers.get("Content-Type", "").split('/')[-1]
    # save image to docs/assets/images/<title>.jpg
    with open(f'docs/assets/images/{slugify(title, "_")}-{timestamp}.{extension}', 'wb') as f:
        f.write(response.content)

import curl_cffi

from markdown.extensions.toc import slugify

images: dict[str, str] = {}

for title, url in images.items():
    # download image with curl_cffi impersonating chrome
    response = curl_cffi.get(url, impersonate='chrome')
    # get image extension from content-type header
    extension = response.headers.get("Content-Type", "").split('/')[-1]
    # save image to docs/assets/images/<title>.jpg
    with open(f'docs/assets/images/{slugify(title, "-")}.{extension}', 'wb') as f:
        f.write(response.content)

import curl_cffi
import time

from markdown.extensions.toc import slugify

images: dict[str, str] = {}


for title, url in images.items():
    # get unix timestamp
    timestamp = int(time.time())

    try:
        # download image with curl_cffi impersonating chrome
        response = curl_cffi.get(url, impersonate='chrome')
    except Exception as e:
        print(f"Error downloading image for {title}: {e}")
        continue

    # get image extension from content-type header
    extension = response.headers.get("Content-Type", "").split('/')[-1]

    # save image to docs/assets/images/<title>.jpg
    image_name = f'{slugify(title, "_")}-{timestamp}.{extension}'
    with open(f'./docs/assets/images/{image_name}', 'wb') as f:
        f.write(response.content)

    # add images to cache as markdown
    with open("./.cache/images.md", "a") as cache:
        cache.write(f"![{title}](site:assets/images/{image_name}){{ .top-list-image }}\n\n")
        cache.write(f"## {title}\n\n")
        cache.write("---\n\n")

import curl_cffi
import time

from markdown.extensions.toc import slugify

images: dict[str, str] = {
    # "Abronia - Shapes Unravel": "https://f4.bcbits.com/img/a2597020737_16.jpg",
    # "Apparat - A Hum of Maybe": "https://f4.bcbits.com/img/a1971940186_16.jpg",
    # "Puscifer - Normal Isn’t": "https://puscifer.com/cdn/shop/files/puscifer_cover_press.jpg",
    # "Thistle Sifter - Forever The Optimist": "https://f4.bcbits.com/img/a3341013214_16.jpg",
    # "Calvin Love - Throw my Shadow to the Sun": "https://propermusic.com/cdn/shop/files/0743407722419.jpg",
    # "Converge - Love is not enough": "https://f4.bcbits.com/img/a1291330267_16.jpg",
    # "Helicon, Al Lover - Arise": "https://f4.bcbits.com/img/a0747300167_10.jpg",
    # "The Ant Band - From Genesis to Reimagination": "https://f4.bcbits.com/img/a0143925967_10.jpg",
    # "Hen Ogledd - DISCOMBOBULATED": "https://narcmagazine.com/wp-content/uploads/2026/02/hen-ogledd.jpg",
    # "Ponte Del Diavolo - De Venom Natura": "https://f4.bcbits.com/img/a3793236782_16.jpg",
    # "New Found Glory - Listen Up!": "https://upload.wikimedia.org/wikipedia/en/3/3e/Listen_Up%21.jpg",
    # "Zahn - Purpur": "https://f4.bcbits.com/img/a2030838000_16.jpg",
    # "Death Of Youth - Nothing Is The Same Anymore": "https://f4.bcbits.com/img/a0769363702_10.jpg",
    # "Bruecken - Years That Answer": "https://f4.bcbits.com/img/a2325173818_10.jpg",
    # "Unverkalt - Héréditaire": "https://f4.bcbits.com/img/a1255436578_10.jpg",
    # "EXEK - Prove The Mountains Move": "https://www.limitedadditionrecords.com/cdn/shop/files/EXEK-ProveTheMountainsMove_grande.jpg",
}


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

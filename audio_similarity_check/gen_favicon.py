from PIL import Image, ImageDraw
img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)
# Background circle
draw.ellipse([4, 4, 60, 60], fill=(103, 80, 164, 255))
# Music note shape
draw.rectangle([28, 12, 36, 48], fill=(255, 255, 255, 255))
draw.rectangle([36, 12, 40, 24], fill=(255, 255, 255, 255))
draw.ellipse([22, 40, 36, 54], fill=(255, 255, 255, 255))
img.save('favicon.ico', format='ICO', sizes=[(16,16), (32,32), (64,64)])
print('favicon.ico created')
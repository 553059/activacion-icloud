from PIL import Image, ImageDraw, ImageFont
import os

out_path = os.path.join(os.path.dirname(__file__), 'assets', 'jarvis_icon.ico')
size = 512
img = Image.new('RGBA', (size, size), (8,25,35,255))
d = ImageDraw.Draw(img)

# cyan/neon circle
circle_radius = int(size * 0.38)
center = (size // 2, size // 2)
bbox = [center[0]-circle_radius, center[1]-circle_radius, center[0]+circle_radius, center[1]+circle_radius]
d.ellipse(bbox, fill=(0,230,230,255))

# inner circle for depth
inner_radius = int(circle_radius * 0.78)
bbox2 = [center[0]-inner_radius, center[1]-inner_radius, center[0]+inner_radius, center[1]+inner_radius]
d.ellipse(bbox2, fill=(6,20,30,255))

# draw a stylized 'J' in neon cyan
try:
    font = ImageFont.truetype("arial.ttf", int(size * 0.36))
except Exception:
    font = ImageFont.load_default()

text = "J"
try:
    bbox_text = d.textbbox((0, 0), text, font=font)
    w = bbox_text[2] - bbox_text[0]
    h = bbox_text[3] - bbox_text[1]
except Exception:
    w, h = font.getsize(text)
text_pos = (center[0]-w//2, center[1]-h//2 - int(size*0.03))
# draw glow by drawing text multiple times
glow_color = (0,200,200,160)
for dx, dy in [(-3,-3),(-2,-2),(-1,-1),(1,1),(2,2),(3,3)]:
    d.text((text_pos[0]+dx, text_pos[1]+dy), text, font=font, fill=glow_color)

# main text
d.text(text_pos, text, font=font, fill=(255,255,255,255))

# ensure assets folder exists
os.makedirs(os.path.dirname(out_path), exist_ok=True)
# save .ico with multiple sizes
img.save(out_path, sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])
print(f"Icono generado en: {out_path}")

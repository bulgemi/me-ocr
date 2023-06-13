import re
from PIL import Image, ImageOps, ImageEnhance


def remove_special_characters(data: str) -> str:
    processed_data = re.sub(r"[^\uAC00-\uD7A30-9a-zA-Z\s]", "", data)
    return processed_data.replace(" ", "")


def gray_scale(image) -> str:
    img = "upload/_image_g.png"
    img_o = Image.open(image)
    img_g = ImageOps.grayscale(img_o)
    img_g.save(img)
    return img


def sharpen(image, factor: int = 2) -> str:
    img = "upload/_image_s.png"
    img_o = Image.open(image)
    enhancer = ImageEnhance.Sharpness(img_o)
    img_s = enhancer.enhance(factor)
    img_s.save(img)
    return img

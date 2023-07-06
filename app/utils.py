import re
from typing import Optional
from difflib import SequenceMatcher
from PIL import Image, ImageOps, ImageEnhance


def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()


def remove_circle_characters(data: str) -> Optional[str]:
    t = data.replace('O', '')
    t = t.replace('o', '')
    t = t.replace('ㅇ', '')
    t = t.replace('@', '')
    t = t.replace('0', '')

    if t.isnumeric():
        return None
    else:
        return t


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
    img_e = enhancer.enhance(factor)
    img_e.save(img)
    return img


def contrast(image, factor: float = 1.5) -> str:
    img = "upload/_image_c.png"
    img_o = Image.open(image)
    enhancer = ImageEnhance.Contrast(img_o)
    img_e = enhancer.enhance(factor)
    img_e.save(img)
    return img


def adjust_image(image,
                 output: str = "upload/_image_a.png",
                 brightness: float = 1.2,
                 contrast: int = 2,
                 sharpness: int = 3) -> str:
    # 이미지 불러오기
    image = Image.open(image)
    # 흑백으로 변환
    grayscale_image = image.convert("L")

    # 라이트벨런스 조절
    enhancer = ImageEnhance.Brightness(grayscale_image)
    light_balanced_image = enhancer.enhance(brightness)

    # 대비 조절
    enhancer = ImageEnhance.Contrast(light_balanced_image)
    contrast_adjusted_image = enhancer.enhance(contrast)

    # 선명도 조절
    enhancer = ImageEnhance.Sharpness(contrast_adjusted_image)
    final_image = enhancer.enhance(sharpness)

    # 조정된 이미지 저장
    final_image.save(output)

    # 결과 이미지 반환
    return output

# server.py
import os
import json
from io import BytesIO
import base64
import os
from collections import OrderedDict

import numpy as np
from flask import (
    Flask,
    render_template,
    send_from_directory,
    request
)
from PIL import Image
import easyocr

from utils import (
    remove_special_characters,
    gray_scale,
    sharpen,
    contrast,
    adjust_image,
    similar
)
from spell import TypoCorrection


app = Flask(__name__, static_folder="static")
app.config['DEBUG'] = True
app.secret_key = 'secret_key-9ed4d409-98dd-422b-9c48-9382da44423a'

if not os.path.exists("upload/"):
    os.mkdir("upload/")


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/submit_image", methods=["GET", "POST"])
def submit_image():
    typo_cor = TypoCorrection()
    index_key = 'base64,'
    img_data = request.data
    # print(f"org_data--->{img_data}")
    img_stringify = str(img_data, 'utf-8')
    # print(f"img--->{img_stringify}")
    img = img_stringify.split(index_key)[1]

    img = base64.b64decode(img)
    img = BytesIO(img)
    img = Image.open(img)
    org_img = 'upload/_image.png'
    img.save(org_img)
    # gray_img = gray_scale(org_img)
    # sharpen_img = sharpen(gray_img)
    # proc_img = contrast(sharpen_img, factor=1.1)
    proc_img = adjust_image(org_img)

    reader = easyocr.Reader(['ko', 'en'])
    ocr_results = reader.readtext(proc_img)

    preprocessed_data = [typo_cor.correction(remove_special_characters(i[1])) for i in ocr_results]
    preprocessed_data_map = OrderedDict()
    for i in ocr_results:
        preprocessed_data_map[typo_cor.correction(remove_special_characters(i[1]))] = i[0]
    # print("=" * 50)
    # for k, v in preprocessed_data_map.items():
    #     print(f"{k}: {v}")
    print(f"{preprocessed_data_map.items()}")
    print(f"{preprocessed_data_map.keys()}")
    preprocessed_data_list = list(preprocessed_data_map.keys())
    print(f"{len(preprocessed_data_list)}")
    print(f"{preprocessed_data_list.index('상호')}")

    print("=" * 50)
    extract_keys = {
        '진료기간': {"min": [20, 20], "max": [30, 30]},
        '진료비총액': {"min": [180, 15], "max": [250, 30]}
    }
    result = list()
    result.append(f"사업자등록번호: {preprocessed_data_list[preprocessed_data_list.index('사업자등록번호')+1]}")
    result.append(f"상호: {preprocessed_data_list[preprocessed_data_list.index('상호')+1]}")
    result.append(f"전화번호: {preprocessed_data_list[preprocessed_data_list.index('전화번호')+1]}")
    temp = preprocessed_data_list[preprocessed_data_list.index('진료비총액')+1:]
    print(temp)
    for t in temp:
        t = t.replace('O', '0')
        t = t.replace('o', '0')
        if t.isnumeric() and not t.startswith('0') and int(t) > 0:
            result.append(f"진료비총액: {t}")
            break

    return json.dumps(result, ensure_ascii=False).encode('utf8'), 200, {'ContentType': 'application/json; charset=utf-8'}

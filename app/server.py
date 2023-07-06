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

    preprocessed_data_map = OrderedDict()
    for i in ocr_results:
        print(f"{remove_special_characters(i[1])} -> {typo_cor.correction(remove_special_characters(i[1]))}")
        preprocessed_data_map[typo_cor.correction(remove_special_characters(i[1]))] = i[0]
    # print("=" * 50)
    # for k, v in preprocessed_data_map.items():
    #     print(f"{k}: {v}")
    preprocessed_data_list = list(preprocessed_data_map.keys())

    result = list()
    registration_number = '사업자등록번호'
    company_name = '상호'
    phone = '전화번호'
    total_expenses = '진료비총액'
    patient_expenses = '환자부담총액'
    total_drug_expenses = '약제비총액'
    my_expenses = '본인부담금'
    insurer_expenses = '보험자부담금'

    if registration_number in preprocessed_data_list:
        money = preprocessed_data_list[preprocessed_data_list.index(registration_number)+1]
        if money.isnumeric():
            result.append(
                f"{registration_number}: {money}"
            )

    if company_name in preprocessed_data_list:
        val = preprocessed_data_list[preprocessed_data_list.index(company_name)+1]
        result.append(f"{company_name}: {val}")

    if phone in preprocessed_data_list:
        val = preprocessed_data_list[preprocessed_data_list.index(phone)+1]
        result.append(f"{phone}: {val}")

    if total_drug_expenses in preprocessed_data_list:
        money = preprocessed_data_list[preprocessed_data_list.index(total_drug_expenses)+1]
        if money.isnumeric():
            result.append(
                f"{total_drug_expenses}: {money}"
            )

    if my_expenses in preprocessed_data_list:
        money = preprocessed_data_list[preprocessed_data_list.index(my_expenses)+1]
        if money.isnumeric():
            result.append(
                f"{my_expenses}: {money}"
            )

    if insurer_expenses in preprocessed_data_list:
        money = preprocessed_data_list[preprocessed_data_list.index(insurer_expenses)+1]
        if money.isnumeric():
            result.append(
                f"{insurer_expenses}: {money}"
            )

    if total_expenses in preprocessed_data_list:
        temp = preprocessed_data_list[preprocessed_data_list.index(total_expenses)+1:]

        for t in temp:
            t = t.replace('O', '0')
            t = t.replace('o', '0')
            t = t.replace('ㅇ', '0')
            if t.isnumeric() and not t.startswith('0') and int(t) > 0:
                result.append(f"{total_expenses}: {t}")
                break

    if patient_expenses in preprocessed_data_list:
        temp = preprocessed_data_list[preprocessed_data_list.index(patient_expenses)+1:]

        for t in temp:
            t = t.replace('O', '0')
            t = t.replace('o', '0')
            t = t.replace('ㅇ', '0')
            if t.isnumeric() and not t.startswith('0') and int(t) > 0:
                result.append(f"{patient_expenses}: {t}")
                break

    return json.dumps(result, ensure_ascii=False).encode('utf8'), 200, {'ContentType': 'application/json; charset=utf-8'}

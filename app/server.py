# server.py
import os
import json
from io import BytesIO
import base64
from collections import OrderedDict
import datetime
import ssl

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
from roi import (
    RoiInfo,
    RoiUtils,
    ExpenseType
)

ssl._create_default_https_context = ssl._create_unverified_context


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

    web_results = list()  # 웹 출력 목록 변수
    start_time = datetime.datetime.now()
    web_results.append(f'[start: {start_time.strftime("%Y-%m-%d %H:%M:%S %fms")}]')
    # typo_cor = TypoCorrection()
    index_key = 'base64,'
    # print(request)
    img_data = request.data
    #print(f"org_data--->{img_data}")
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

    if True:
        ocr_results = reader.readtext(org_img, detail=2)  # simple image
    else:
        ocr_results = reader.readtext(proc_img)

    # print(ocr_results)
    middle_time = datetime.datetime.now()
    web_results.append(f'[middle_time: {middle_time.strftime("%Y-%m-%d %H:%M:%S %fms")}, elapse_time: {(middle_time-start_time).total_seconds()} seconds]\n')

    expense_type = None
    max_outer_contour = RoiInfo()
    roi_utils = RoiUtils()
    conv_items = list()
    for item in ocr_results:  # EasyOCR 추출 데이타 원본에서 분석용 데이타 포맷으로 변환처리
        conv_item = roi_utils.convert_item_dataclass(item)
        # print(item)
        # print(conv_item)
        result = roi_utils.check_expense_type(conv_item)  # type check
        if result is not None:
              expense_type = ExpenseType(result)  # set expense type
        roi_utils.set_max_outer_contour(max_outer_contour, conv_item)  # set max countour
        conv_items.append(conv_item)  # convert data append to list

    if expense_type == ExpenseType.MEDICAL:  # 진료비 영수증 Type 처리
        key_strs = roi_utils.mtype_key_strs
        extract_data = roi_utils.extract_medical_data(key_strs, conv_items, max_outer_contour)  # 값 추출처리

        for data in extract_data:
            # print(data)
            web_results.append(f'{data.key_str} : [{data.value}, 정확도 ({data.accurate})]')
        refine_data = roi_utils.refine_extract_data(expense_type, extract_data)  # 결과 값 보정처리
    elif expense_type == ExpenseType.PHARMACEUTICAL :  # 약제비계산서 Type 처리
        key_strs = roi_utils.ptype_key_strs
        extract_data = roi_utils.extract_pharmaceutical_data(key_strs, conv_items, max_outer_contour)  # 값 추출처리

        for data in extract_data:
            # print(data)
            web_results.append(f'{data.key_str} : [{data.value}, 정확도 ({data.accurate})]')
        refine_data = roi_utils.refine_extract_data(expense_type, extract_data)  # 결과 값 보정처리
    else:
        refine_data = list()
        print('Unknown Expense Type !!!')
        web_results.append({"Unknown": "Expense Type"})

    web_results.append("\n----- refined data -----\n")

    for data in refine_data:
        # print(data)
        web_results.append(f'{data.key_str}: [{data.value}, 정확도 ({data.accurate})]')

    end_time = datetime.datetime.now()
    web_results.append(f'\n[end_time: {end_time.strftime("%Y-%m-%d %H:%M:%S %fms")}, elapse_time: {(end_time-start_time).total_seconds()} seconds]')

    return json.dumps(web_results, indent=2, ensure_ascii=False).encode('utf8'), 200, {'ContentType': 'application/json; charset=utf-8'}

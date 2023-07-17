# server.py
import os
import json
from io import BytesIO
import base64
import os
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
import datetime
from typing import Optional

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


@dataclass
class ROI_Info:   # selected ROI Position and Calculated Info
  top: Optional[int] = None
  bottom: Optional[int] = None
  left: Optional[int] = None
  right: Optional[int] = None
  width: Optional[int] = None
  height: Optional[int] = None


@dataclass(order=True)
class DataInfo:   # Data structure for Selected ROI Object by EasyOCR
  rect: ROI_Info = field(default_factory=ROI_Info)
  value: Optional[str] = None
  accurate: Optional[float] = None
  data: list = field(default_factory=list)


def convert_item_dataclass(item) -> DataInfo:
    """
    프로그램을 위한 Class로 convert 하는 함수

    :parameter
    item :  EasyOCR로 부터 분류된 raw data info
    """
    datainfo = DataInfo()

    pos, value, accurate = item
    # Position
    datainfo.rect.top = min(pos[0][1], pos[1][1])
    datainfo.rect.bottom = max(pos[2][1],pos[3][1])
    datainfo.rect.left = min(pos[0][0], pos[1][0])
    datainfo.rect.right = max(pos[2][0], pos[2][0])
    datainfo.rect.width = datainfo.rect.right - datainfo.rect.left
    datainfo.rect.height = datainfo.rect.bottom - datainfo.rect.top
    # Data
    datainfo.value = value.replace(' ', '')
    datainfo.accurate = accurate
    # Raw Data
    datainfo.data = list(item)
    return datainfo


def set_max_outer_contour(contour, datainfo):
    """
    약제비/진료비 영수증 추출 데이타 위치로 계산된 최대 rectangle 계산하기

    :parameter
    contour :  최대 rectangle 정보 셋팅 변수
    datainfo : EasyOCR로 부터 conv_data
    """
    contour.top = min(contour.top, datainfo.rect.top) if contour.top is not None else datainfo.rect.top
    contour.bottom = max(contour.bottom, datainfo.rect.bottom) if contour.bottom is not None else datainfo.rect.bottom
    contour.left = min(contour.left, datainfo.rect.left) if contour.left is not None else datainfo.rect.left
    contour.right = max(contour.right, datainfo.rect.right) if contour.right is not None else datainfo.rect.right
    contour.width = contour.right - contour.left
    contour.height = contour.bottom - contour.top


type_key_str = ('약제비', '진료비')


class ExpenseType(Enum):  # 영수증 type 관리용 Enum Class
    PHARMACEUTICAL = 0
    MEDICAL = 1
    UNKNOWN = 2


def check_expense_type(datainfo) -> Optional[int]:
    """
    영수증의 Type을 체크하는 함수

    :parameter
        datainfo: EasyOCR로 부터 conv_data
    :returns
        index:
    """
    for idx, key in enumerate(list(type_key_str)):
        if key in datainfo.value:
            # print('check : {}, {}, {}, {}'.format(idx, ExpenseType(idx), key, datainfo.value))
            return idx
    return None


# 약제비계산서 keywords
ptype_key_strs = ('환자성명',
                  '환자정보',
                  '조제일자',
                  '본인부담금',
                  '분인부담금',
                  '보험자부담금',
                  '비급여',
                  '사업가등록번호',
                  '자업지등록번호',
                  '사업자등록번호',
                  '사업장등록번호',
                  '상호',
                  '호')
# 진료비영수증 keywords
mtype_key_strs = ('환자성명',
                  '진료기간',
                  '본인부담금',
                  '합계',
                  '함계',
                  '사업가등록번호',
                  '사업자등록번호',
                  '사업장등록번호',
                  '상호')  # 합계는 width/2 보다 작은 값으로 선택


@dataclass
class OCRDataInfo:   # Data structure for expenses
  key_str: Optional[str] = None
  rect: ROI_Info = field(default_factory=ROI_Info)
  value: Optional[str] = None
  accurate: Optional[float] = None


def get_datainfo_from_value(key, datainfos, max_contour):
    """
    약제비/진료비 영수증의 정보중에서 keyword를 포함하고 있는 conv_data를 얻어오는 함수

    :parameter
        key: 정보를 추출할 keyword
        datainfos: EasyOCR로 부터 conv_data list
        max_contour: 진료비 영수증 추출 데이타 위치로 계산된 최대 rectangle 정보
    """
    for item in datainfos:
        if key == '합계' or key == '함계':  # 진료비계산서의 경우 2개의 합계 정보 중 좌측 합계를 사용한다.
            if key in item.value and item.rect.left < int(max_contour.width / 2):
                print('get_datainfo_from_value key : {}, value : {} item.rect.left : {} max_contour.width/2 : {}'.format(key, item.value, item.rect.left, int(max_contour.width / 2)))
                return item
        elif key in item.value:
            if key == '호' or key == '상호':
                if key == item.value:
                    return item
            else :
                return item
    return None


def ext_next_line_data(baseinfo, datainfos):
    """
    진료비 영수증의 컬럼 바로 아래 Line의 컬럼 값을 추출하는 함수

    :parameter
        baseinfo : keyword를 포함하고 있는 conv_data info
        datainfos : EasyOCR로 부터 conv_data list
    """
    if baseinfo is None:
        return None

    items = list()
    for item in datainfos:
        if (max(0, baseinfo.rect.left - int(baseinfo.rect.width * 2.5)) <= item.rect.left and
                (baseinfo.rect.right + int(baseinfo.rect.width * 2.5)) >= item.rect.right and
                (baseinfo.rect.bottom - int(baseinfo.rect.height/2)) <= item.rect.top and
                (baseinfo.rect.bottom + int(baseinfo.rect.height*1.5)) >= item.rect.bottom):
            # print('next_line : {}'.format(item))
            items.append(item)
    return items


def ext_next_column_data(key, baseinfo, datainfos):
    """
    약제비/진료비 영수증의 동일 Line의 바로 옆의 컬럼 값을 추출하는 함수

    :parameter
        key:  정보를 추출할 keyword
        baseinfo: keyword를 포함하고 있는 conv_data info
        datainfos: EasyOCR로 부터 conv_data list
    """
    if baseinfo is None:
        return None

    for item in datainfos:
        if key in ['사업자등록번호', '사업가등록번호', '사업장등록번호']:
            if (
                    (baseinfo.rect.right <= item.rect.left) and
                    ((baseinfo.rect.right + int(baseinfo.rect.width*2)) >= item.rect.right) and
                    ((baseinfo.rect.top - int(baseinfo.rect.height/2)) <= item.rect.top) and
                    ((baseinfo.rect.bottom + int(baseinfo.rect.height/2)) >= item.rect.bottom)
            ):
                #  print('next_column : {}'.format(item))
                return item
        elif key == '상호':
             if (
                     (baseinfo.rect.right <= item.rect.left) and
                     ((baseinfo.rect.right + int(baseinfo.rect.width*10)) >= item.rect.right) and
                     ((baseinfo.rect.top - int(baseinfo.rect.height/2)) <= item.rect.top) and
                     ((baseinfo.rect.bottom + int(baseinfo.rect.height/2)) >= item.rect.bottom)
             ):
                # print('next_column : {}'.format(item))
                return item
        elif key == '호':
             if (
                     (baseinfo.rect.right <= item.rect.left) and
                     ((baseinfo.rect.right + int(baseinfo.rect.width*20)) >= item.rect.right) and
                     ((baseinfo.rect.top - int(baseinfo.rect.height*(2/3))) <= item.rect.top) and
                     ((baseinfo.rect.bottom + int(baseinfo.rect.height*(2/3))) >= item.rect.bottom)
             ):
                # print('next_column : {}'.format(item))
                return item
        else:
            if (
                    (baseinfo.rect.right <= item.rect.left) and
                    ((baseinfo.rect.right + int(baseinfo.rect.width*3.5)) >= item.rect.right) and
                    ((baseinfo.rect.top - int(baseinfo.rect.height*(2/3))) <= item.rect.top) and
                    ((baseinfo.rect.bottom + int(baseinfo.rect.height*(2/3))) >= item.rect.bottom)
            ):
                #  print('next_column : {}'.format(item))
                return item
    return None


def ext_next_columns_data(key, baseinfo, datainfos):
    """
    진료비 영수증의 동일 Line의 복수 컬럼 얻기 : 합계 컬럼

    :parameter
        key:  합계 or 함계(분석오류데이타 보정위함)
        baseinfo: keyword를 포함하고 있는 conv_data info
        datainfos: EasyOCR로 부터 conv_data list
    """
    tmp_baseinfo = baseinfo
    columns_data = list()

    if baseinfo is None:
        return columns_data

    for item in datainfos:
        if (
                (tmp_baseinfo.rect.right <= item.rect.left) and
                ((tmp_baseinfo.rect.top - int(tmp_baseinfo.rect.height/2)) <= item.rect.top) and
                ((tmp_baseinfo.rect.bottom + int(tmp_baseinfo.rect.height/2)) >= item.rect.bottom)
        ):
            # print('ext_next_columns_data : {}', item)
            columns_data.append(item)
    return columns_data


def extract_medical_data(keys, datainfos, max_contour):
    """
    진료비영수증 정보 추출 함수

    :parameter
        keys: 정보를 추출할 keyword list
        datainfos: EasyOCR로 부터 conv_data list
        max_contour: 진료비 영수증 추출 데이타 위치로 계산된 최대 rectangle 정보
    :returns
    """
    extracts = list()

    for key in list(keys):
        tmp = get_datainfo_from_value(key, datainfos, max_contour)
        # print('extract_medical_data key : {}, {}'.format(key,tmp))
        if key in ['환자성명', '진료기간']:
            tmp2 = ext_next_line_data(tmp, datainfos)

            if tmp2 is not None:
                for item in tmp2:  # keyword 연관 데이타 발견되었으면 저장
                    tmp3 = OCRDataInfo()

                    tmp3.key_str = key
                    tmp3.rect = item.rect
                    tmp3.value = item.value
                    tmp3.accurate = item.accurate
                    extracts.append(tmp3)
        elif key in ['사업자등록번호', '사업가등록번호', '사업장등록번호', '상호']:
            tmp2 = ext_next_column_data(key, tmp, datainfos)

            if tmp2 is not None:  # keyword 연관 데이타 발견되었으면 저장
                tmp3 = OCRDataInfo()

                tmp3.key_str = key
                tmp3.rect = tmp2.rect
                tmp3.value = tmp2.value
                tmp3.accurate = tmp2.accurate
                extracts.append(tmp3)
        elif key in ['합계', '함계']:
            tmp2 = ext_next_columns_data(key, tmp, datainfos)
            # print("tmp2 : {}".format(tmp2))
            if tmp2 is not None:
                for column_data in tmp2:  # 데이타가 있을 경우만 처리한다.
                    summary_key_strs = ['본인부담금', '공단부담금', '선택진료']
                    tmp3 = OCRDataInfo()

                    flag_exist = False
                    for summary_key in summary_key_strs:
                        tmp4 = get_datainfo_from_value(summary_key, datainfos, max_contour)
                        # print("tmp4 : {}".format(tmp4))
                        if tmp4 is None:
                            continue

                        if tmp4.rect.left <= column_data.rect.left and\
                                tmp4.rect.right + int(tmp4.rect.width/2) >= column_data.rect.right:
                            tmp3.key_str = summary_key
                            tmp3.rect = column_data.rect
                            tmp3.value = column_data.value
                            tmp3.accurate = column_data.accurate
                            # print("tmp3 : {}".format(tmp3))
                            extracts.append(tmp3)
                            flag_exist = True
                            break
                    if flag_exist is False:
                        tmp3.key_str = '비급여-선택진료료이외'
                        tmp3.rect = column_data.rect
                        tmp3.value = column_data.value
                        tmp3.accurate = column_data.accurate
                        extracts.append(tmp3)
                    else:
                        flag_exist = False
    return extracts


def extract_pharmaceutical_data(keys, datainfos, max_contour):
    """
    약제비계산서 정보 추출 함수

    :parameter
        keys: 정보를 추출할 keyword list
        datainfos: EasyOCR로 부터 conv_data list
        max_contour: 약제비계산서 추출 데이타 위치로 계산된 최대 rectangle 정보
    """
    extracts = list()

    for key in list(keys):
        tmp = get_datainfo_from_value(key, datainfos, max_contour)
        # print('extract_pharmaceutical_data key : {}, {}'.format(key,tmp))
        tmp2 = ext_next_column_data(key, tmp, datainfos)

        if tmp2 is not None:  # keyword 연관 데이타 발견되었으면 저장
            tmp3 = OCRDataInfo()

            tmp3.key_str = key
            tmp3.rect = tmp2.rect
            tmp3.value = tmp2.value
            tmp3.accurate = tmp2.accurate
            extracts.append(tmp3)
    return extracts


def refine_extract_data(expense_type, extracts_data):
    """
    최종 추출 데이타를 기준으로 유사추출 정보 및 Value 보완처리 함수

    :parameter
        expense_type: 영수증 type
        extracts_data: 추출 데이타 정보 목록
    """
    refines = list()

    for idx, data in enumerate(extracts_data):
        if expense_type == ExpenseType.MEDICAL:  # 진료비 영수증 Type 처리
            if data.key_str == '함계':
                data.key_str = '합계'
            elif data.key_str in ['사업가등록번호', '사업장등록번호']:
                data.key_str = '사업자등록번호'
            elif data.key_str == '진료기간':
                # 진료기간이 from - to 인 경우를 체크
                if (idx + 1) < len(extracts_data) and extracts_data[idx+1].key_str == '진료기간':
                    data.value += extracts_data[idx+1].value
                    extracts_data.pop(idx+1)
        elif expense_type == ExpenseType.PHARMACEUTICAL:  # 약제비계산서 Type 처리
            if data.key_str == '분인부담금':
                data.key_str = '본인부담금'
            elif data.key_str in ['사업가등록번호', '자업지등록번호', '사업장등록번호']:
                data.key_str = '사업자등록번호'
            elif data.key_str == '호':
                data.key_str = '상호'
            elif data.key_str == '환자성명':
                for index in range(idx+1, len(extracts_data)):
                    if extracts_data[index].key_str == '환자정보':
                        data.value = extracts_data[index].value
                        extracts_data.pop(index)
                        break
            elif data.key_str == '환자정보':
                data.key_str = '환자성명'
        # print(data)
        refines.append(data)
    return refines


@app.route("/submit_image", methods=["GET", "POST"])
def submit_image():

    web_results = list()  # 웹 출력 목록 변수
    start_time = datetime.datetime.now()
    web_results.append(f'[[ start : {start_time.strftime("%Y-%m-%d %H:%M:%S %fms")} ]]')
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
    web_results.append(f'[[ middle_time : {middle_time.strftime("%Y-%m-%d %H:%M:%S %fms")}, elapse_time : {(middle_time-start_time).total_seconds()} seconds ]]')

    expense_type = None
    max_outer_contour = ROI_Info()
    conv_items = list()
    for item in ocr_results:  # EasyOCR 추출 데이타 원본에서 분석용 데이타 포맷으로 변환처리
        conv_item = convert_item_dataclass(item)
        # print(item)
        # print(conv_item)
        result = check_expense_type(conv_item)  # type check
        if result is not None:
              expense_type = ExpenseType(result)  # set expense type
        set_max_outer_contour(max_outer_contour, conv_item)  # set max countour
        conv_items.append(conv_item)  # convert data append to list

    if expense_type == ExpenseType.MEDICAL:  # 진료비 영수증 Type 처리
        key_strs = mtype_key_strs
        extract_data = extract_medical_data(key_strs, conv_items, max_outer_contour)  # 값 추출처리

        for data in extract_data:
            # print(data)
            web_results.append(f'{data.key_str} : [{data.value}, 정확도 ({data.accurate})]')
        refine_data = refine_extract_data(expense_type, extract_data)  # 결과 값 보정처리
    elif expense_type == ExpenseType.PHARMACEUTICAL :  # 약제비계산서 Type 처리
        key_strs = ptype_key_strs
        extract_data = extract_pharmaceutical_data(key_strs, conv_items, max_outer_contour)  # 값 추출처리

        for data in extract_data:
            # print(data)
            web_results.append(f'{data.key_str} : [{data.value}, 정확도 ({data.accurate})]')
        refine_data = refine_extract_data(expense_type, extract_data)  # 결과 값 보정처리
    else:
        refine_data = list()
        print('Unknown Expense Type !!!')
        web_results.append({"Unknown": "Expense Type"})

    web_results.append(":")
    web_results.append("-- refined data -- : ---------------")
    web_results.append(":")

    for data in refine_data:
        # print(data)
        web_results.append(f'{data.key_str} : [{data.value}, 정확도 ({data.accurate})]')

    end_time = datetime.datetime.now()
    web_results.append(f'[[ end_time : {end_time.strftime("%Y-%m-%d %H:%M:%S %fms")}, elapse_time : {(end_time-start_time).total_seconds()} seconds ]]')

    return json.dumps(web_results, indent=2, ensure_ascii=False).encode('utf8'), 200, {'ContentType': 'application/json; charset=utf-8'}

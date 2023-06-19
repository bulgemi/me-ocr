# server.py
import os
import json
from io import BytesIO
import base64
import os
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
    adjust_image
)


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

    print("=" * 50)
    for r in ocr_results:
        print(f"{r}, {remove_special_characters(r[1])}")
    preprocessed_data = [remove_special_characters(i[1]) for i in ocr_results]

    return json.dumps(preprocessed_data, ensure_ascii=False).encode('utf8'), 200, {'ContentType': 'application/json; charset=utf-8'}

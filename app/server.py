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
    img.save('upload/_image.png')

    reader = easyocr.Reader(['ko', 'en'])
    ocr_results = reader.readtext('upload/_image.png')

    print("="*50)
    print(f"({type(ocr_results)}){ocr_results}")

    return json.dumps([i[1] for i in ocr_results]), 200, {'ContentType': 'application/json'}

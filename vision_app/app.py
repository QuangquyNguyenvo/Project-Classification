from flask import Flask, request, render_template, redirect, url_for, session
from google.cloud import vision
from google.cloud.vision_v1 import types
from PIL import Image, ImageDraw, ImageFont
import matplotlib.font_manager as fm
import io
import os
import requests

app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'uploads')

# Đặt đường dẫn tới file JSON chứa Google Cloud API Key
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'key.json'

# Tạo thư mục upload nếu chưa tồn tại
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def determine_waste_type(labels):
    organic_labels = ['food', 'fruit', 'vegetable', 'plant', 'organic', 'compost', 'biodegradable', 'leaf', 'wood', 'flower', 'seed', 'grain', 'bread', 'meat', 'dairy', 'egg','human','animal']
    inorganic_labels = ['plastic', 'glass', 'metal', 'paper', 'cardboard', 'aluminum', 'steel', 'tin', 'ceramic', 'concrete', 'stone', 'rubber', 'leather','rubber band']
    electronic_labels = ['electronic', 'computer', 'phone', 'circuit', 'laptop', 'monitor', 'keyboard', 'printer', 'cable', 'battery', 'chip', 'motherboard', 'speaker', 'headphone', 'camera', 'television', 'remote']

    for label in labels:
        description = label.description.lower()
        if any(word in description for word in organic_labels):
            return 'Hữu cơ'
        elif any(word in description for word in inorganic_labels):
            return 'Vô cơ'
        elif any(word in description for word in electronic_labels):
            return 'Linh kiện điện tử'

    return 'Khác'

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' in request.files and request.files['file'].filename != '':
            file = request.files['file']
            filename = file.filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            labels, modified_image_path = detect_labels_and_objects(filepath)
            session['labels'] = [(label.description, label.score) for label in labels]
            session['image_url'] = modified_image_path
            waste_type = determine_waste_type(labels)
            session['waste_type'] = waste_type
            return redirect(url_for('result'))
        elif 'url' in request.form and request.form['url'] != '':
            image_url = request.form['url']
            response = requests.get(image_url)
            img = Image.open(io.BytesIO(response.content))
            filename = 'temp_image.jpg'
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            img.save(filepath)
            labels, modified_image_path = detect_labels_and_objects(filepath)
            session['labels'] = [(label.description, label.score) for label in labels]
            session['image_url'] = modified_image_path
            waste_type = determine_waste_type(labels)
            session['waste_type'] = waste_type
            return redirect(url_for('result'))
    return render_template('index.html')

@app.route('/result')
def result():
    labels = session.get('labels', [])
    image_filename = os.path.basename(session.get('image_url', ''))
    waste_type = session.get('waste_type', 'Khác')
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
    return render_template('result.html', labels=labels, image_filename=image_filename, image_path=image_path, waste_type=waste_type)

def detect_labels_and_objects(path):
    client = vision.ImageAnnotatorClient()
    with io.open(path, 'rb') as image_file:
        content = image_file.read()
    image = types.Image(content=content)
    label_response = client.label_detection(image=image)
    labels = label_response.label_annotations

    object_response = client.object_localization(image=image)
    objects = object_response.localized_object_annotations
    im = Image.open(path)
    im = im.resize((640, 480))
    draw = ImageDraw.Draw(im)
    # sửa font mặc định lại xíu
    default_font_path = fm.findSystemFonts()[0]
    font_size = 20
    font = ImageFont.truetype(default_font_path, font_size)

    for object_ in objects:
        box = [(vertex.x * im.width, vertex.y * im.height) for vertex in object_.bounding_poly.normalized_vertices]
        draw.line(box + [box[0]], width=5, fill='red')
        draw.text((box[0][0], box[0][1] - 30), object_.name, fill='black', font=font)

    # rename lại ảnh
    modified_image_filename = 'modified_' + os.path.basename(path)
    modified_image_path = os.path.join(app.config['UPLOAD_FOLDER'], modified_image_filename)
    im.save(modified_image_path)
    return labels, modified_image_path

if __name__ == '__main__':
    app.run(debug=True)

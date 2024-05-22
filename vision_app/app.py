from flask import Flask, request, render_template, redirect, url_for, session
from google.cloud import vision
from google.cloud.vision_v1 import types
from PIL import Image, ImageDraw, ImageFont
import io
import os
import base64

import os

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.secret_key = 'supersecretkey'

# Đặt đường dẫn tới file JSON chứa Google Cloud API Key
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'key.json'

# Tạo thư mục upload nếu chưa tồn tại
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])
# tạo list py
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
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        if file:
            filename = file.filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
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
    image_url = session.get('image_url', '')
    waste_type = session.get('waste_type', 'Khác')
    return render_template('result.html', labels=labels, image_url=image_url, waste_type=waste_type)

def detect_labels_and_objects(path):
    client = vision.ImageAnnotatorClient()
    with io.open(path, 'rb') as image_file:
        content = image_file.read()
    image = types.Image(content=content)

    # Detect labels
    label_response = client.label_detection(image=image)
    labels = label_response.label_annotations

    # Detect objects
    object_response = client.object_localization(image=image)
    objects = object_response.localized_object_annotations

    im = Image.open(path)
    draw = ImageDraw.Draw(im)
    font = ImageFont.load_default()

    for object_ in objects:
        box = [(vertex.x * im.width, vertex.y * im.height) for vertex in object_.bounding_poly.normalized_vertices]
        draw.line(box + [box[0]], width=5, fill='red')
        draw.text((box[0][0], box[0][1] - 10), object_.name, fill='blue', font=font)
    
    # Lưu tệp ảnh đã được sửa đổi với tên mới
    modified_image_filename = 'modified_' + os.path.basename(path)
    modified_image_path = os.path.join(app.config['UPLOAD_FOLDER'], modified_image_filename)
    im.save(modified_image_path)
    return labels, modified_image_path

if __name__ == '__main__':
    app.run(debug=True)

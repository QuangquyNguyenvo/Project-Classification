from flask import Flask, request, render_template, redirect, url_for, session
from google.cloud import vision
from google.cloud.vision_v1 import types
from PIL import Image, ImageDraw, ImageFont
import matplotlib.font_manager as fm
import io, os, requests

app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'key.json'

# Initialize counters for each waste type
counters = {
    'total_images': 0,
    'successful_classifications': 0,
    'failed_classifications': 0,
    'Hữu cơ': 0,
    'Vô cơ': 0,
    'Y tế': 0,
    'Linh kiện điện tử': 0,
    'Khác': 0
}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif', 'jfif', 'webp'}

def determine_waste_type(labels):
    organic_labels = ['food', 'fruit', 'vegetable', 'plant', 'organic', 'compost', 'biodegradable', 'leaf', 'wood', 'flower', 'seed', 'grain', 'bread', 'meat', 'dairy', 'egg','human','animal']
    inorganic_labels = ['plastic', 'glass', 'metal', 'paper', 'cardboard', 'aluminum', 'steel', 'tin', 'ceramic', 'concrete', 'stone', 'rubber', 'leather','rubber band']
    electronic_labels = ['electronic', 'computer', 'phone', 'circuit', 'laptop', 'monitor', 'keyboard', 'printer', 'cable', 'battery', 'chip', 'motherboard', 'speaker', 'headphone', 'camera', 'television', 'remote']
    medical_labels = ['medical', 'syringe', 'needle', 'bandage', 'glove', 'mask', 'pill', 'medication', 'tablet', 'surgical', 'first aid', 'medicine', 'hospital', 'clinic', 'blood', 'plasma', 'vaccine', 'test tube']

    for label in labels:
        description = label.description.lower()
        if any(word in description for word in organic_labels):
            return 'Hữu cơ'
        elif any(word in description for word in inorganic_labels):
            return 'Vô cơ'
        elif any(word in description for word in electronic_labels):
            return 'Linh kiện điện tử'
        elif any(word in description for word in medical_labels):
            return 'Y tế'
    return 'Khác'

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files.get('file') or request.files.get('webcam_image')
        url = request.form.get('url')
        counters['total_images'] += 1
        if (file and file.filename and allowed_file(file.filename)) or (url and url.strip()):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded_image.jpg')
            if file:
                file.save(filepath)
            else:
                Image.open(io.BytesIO(requests.get(url).content)).save(filepath)
            labels, modified_image_path = detect_labels_and_objects(filepath)
            session['labels'] = [(label.description, label.score) for label in labels]
            session['image_url'] = modified_image_path
            waste_type = determine_waste_type(labels)
            session['waste_type'] = waste_type

            # Update the counters
            counters[waste_type] += 1
            counters['successful_classifications'] += 1
        else:
            counters['failed_classifications'] += 1

        return redirect(url_for('result'))

    return render_template('index.html', counters=counters)

@app.route('/result')
def result():
    labels = session.get('labels', [])
    image_filename = os.path.basename(session.get('image_url', ''))
    waste_type = session.get('waste_type', 'Khác')

    return render_template('result.html', labels=labels, image_filename=image_filename, waste_type=waste_type, **counters)

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
    im = im.resize((800, 600))
    draw = ImageDraw.Draw(im)
    default_font_path = fm.findSystemFonts()[0]
    font_size = 20
    font = ImageFont.truetype(default_font_path, font_size)

    for object_ in objects:
        box = [(vertex.x * im.width, vertex.y * im.height) for vertex in object_.bounding_poly.normalized_vertices]
        draw.line(box + [box[0]], width=5, fill='red')
        text_position = (box[0][0] + 10, box[0][1] - 30)
        draw.text(text_position, object_.name, fill='black', font=font)
        draw.text((text_position[0], text_position[1] + 25), f"", fill='black', font=font)

    modified_image_filename = 'modified_uploaded_image.jpg'
    modified_image_path = os.path.join(app.config['UPLOAD_FOLDER'], modified_image_filename)
    im.save(modified_image_path)
    return labels, modified_image_path

@app.route('/about')
def about():
    return render_template('about.html')

if __name__ == '__main__':
    app.run(debug=True)

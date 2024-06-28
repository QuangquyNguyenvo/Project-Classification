from flask import Flask, request, render_template, redirect, url_for, session, jsonify
from PIL import Image, ImageDraw, ImageFont
import matplotlib.font_manager as fm
import io, os, requests, json
import google.generativeai as genai
import cv2
import numpy as np

app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
os.environ['GOOGLE_API_KEY'] = 'AIzaSyDokXpf-6hNH7Rzjynbnj4rphFXfqNA9u4'

genai.configure(api_key=os.environ['GOOGLE_API_KEY'])

counters = {
    'total_images': 0,
    'successful_classifications': 0,
    'Không xác định': 0,
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
    organic_labels = ['food', 'fruit', 'vegetable', 'plant', 'organic', 'compost', 'biodegradable', 'leaf', 'wood', 'flower', 'seed', 'grain', 'bread', 'meat', 'dairy', 'egg', 'human', 'animal']
    inorganic_labels = ['plastic', 'glass', 'metal', 'paper', 'cardboard', 'aluminum', 'steel', 'tin', 'ceramic', 'concrete', 'stone', 'rubber', 'leather', 'rubber band']
    electronic_labels = ['electronic', 'computer', 'phone', 'circuit', 'laptop', 'monitor', 'keyboard', 'printer', 'cable', 'battery', 'chip', 'motherboard', 'speaker', 'headphone', 'camera', 'television', 'remote']
    medical_labels = ['medical', 'syringe', 'needle', 'bandage', 'glove', 'mask', 'pill', 'medication', 'tablet', 'surgical', 'first aid', 'medicine', 'hospital', 'clinic', 'blood', 'plasma', 'vaccine', 'test tube']

    for label in labels:
        if any(word in label.lower() for word in organic_labels):
            return 'Hữu cơ'
        elif any(word in label.lower() for word in inorganic_labels):
            return 'Vô cơ'
        elif any(word in label.lower() for word in electronic_labels):
            return 'Linh kiện điện tử'
        elif any(word in label.lower() for word in medical_labels):
            return 'Y tế'
    return 'Khác'

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files.get('file')
        url = request.form.get('url')
        counters['total_images'] += 1
        if file and allowed_file(file.filename):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded_image.jpg')
            file.save(filepath)
            result, modified_image_path = detect_labels_and_objects(filepath)
            waste_type = result['waste_type'] or 'Khác'
            counters['successful_classifications'] += 1
            counters[waste_type] = counters.get(waste_type, 0) + 1
            session['objects'] = result['objects']
            session['waste_type'] = waste_type
            session['explanation'] = result.get('explanation', '')
            session['image_url'] = modified_image_path
            session['initial_waste_type'] = waste_type  
            return redirect(url_for('result'))
        elif url and url.strip():
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded_image.jpg')
            Image.open(io.BytesIO(requests.get(url).content)).save(filepath)
            result, modified_image_path = detect_labels_and_objects(filepath)
            waste_type = result['waste_type'] or 'Khác'
            counters['successful_classifications'] += 1
            counters[waste_type] = counters.get(waste_type, 0) + 1
            session['objects'] = result['objects']
            session['waste_type'] = waste_type
            session['explanation'] = result.get('explanation', '')
            session['image_url'] = modified_image_path
            session['initial_waste_type'] = waste_type  
            return redirect(url_for('result'))
        else:
            counters['Không xác định'] += 1
    return render_template('index.html', counters=counters)

@app.route('/result')
def result():
    return render_template('result.html', 
                           objects=session.get('objects', []), 
                           image_filename=os.path.basename(session.get('image_url', '')), 
                           waste_type=session.get('waste_type', 'Không xác định'), 
                           explanation=session.get('explanation', ''), 
                           counters=counters)

@app.route('/get_counters', methods=['GET'])
def get_counters():
    return jsonify({'counters': counters})

def detect_labels_and_objects(path):
    model = genai.GenerativeModel('gemini-1.5-pro-001')
    image = Image.open(path)
    resized_image = image.resize((640, 480))
    resized_image_path = os.path.join(app.config['UPLOAD_FOLDER'], 'modified_uploaded_image.jpg')
    resized_image.save(resized_image_path)
    prompt = (
        "nhận diện hình ảnh sau và trả lời thẳng ra câu hỏi sau:\n"
        "1. Đây là hình ảnh của vật thể gì?\n"
        "2. Nếu nó là rác, nó thuộc loại rác nào?: Hữu cơ , Vô cơ , Y tế , Linh kiện điện tử , nếu không nằm trong 4 loại kia thì cứ trả về kết quả Khác cho dù nó không phải là rác.\n"
        "kết quả được đưa về dưới dạng Python với từ khoá 'objects', 'waste_type'.\n"
        "ví dụ nếu là chai nhựa thì trả về là Chai nhựa chứ không phải là ['Chai Nhựa']\n"
        "nếu là vật liệu vô cơ kết thì kết quả trả về là tên vật + chất liệu\n"
        "Nếu là hữu cơ thì mô tả thêm ví dụ thay vì là táo thì sẽ là Quả táo màu đỏ (hoặc màu gì đó bạn nhìn thấy được)\n"
        "Đừng trả lời thừa dấu ví dụ như Hữu cơ' thì hãy trả về kết quả là Hữu Cơ\n"
        "Nếu kết quả nhận được là một nhân vật hoạt hình/ anime nữa thì hãy trả về kết quả là Gái alimi\n"
        "Còn nếu nhân vật là một nhân vật tóc hồng thì bạn hãy kiểm tra xem đó có phải Bocchi trong anime/manga Bocchi The Rock không (hoặc trong tên file ảnh có chữ bocchi hoặc Gotoh Hitori) thì trả về kết quả là vợ của thằng Quangquy Nguyenvo"
    )
    contents = [prompt, resized_image]
    response = model.generate_content(contents)
    try:
        json_start = response.text.find('{')
        json_end = response.text.rfind('}') + 1
        json_str = response.text[json_start:json_end]
        result = json.loads(json_str)
        if isinstance(result['objects'], str):
            result['objects'] = eval(result['objects'])
    except (json.JSONDecodeError, ValueError):
        result = {'objects': [], 'waste_type': None, 'explanation': ''}
        lines = response.text.split('\n')
        for line in lines:
            if 'objects' in line.lower():
                objects_str = line.split(':')[1].strip()
                result['objects'] = eval(objects_str)
            elif 'waste_type' in line.lower():
                result['waste_type'] = line.split(':')[1].strip().strip("'")
            else:
                result['explanation'] += line + '\n'
    if not result['objects']:
        result['objects'] = ['Không nhận diện được vật thể']
    if not result['waste_type']:
        result['waste_type'] = 'Không xác định'
    return result, resized_image_path

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/update_result', methods=['POST'])
def update_result():
    selected_waste_type = request.form.get('selected_waste_type')
    initial_waste_type = session.get('initial_waste_type', 'Không xác định')

    if selected_waste_type and selected_waste_type in counters:
        if initial_waste_type != selected_waste_type:
            counters[initial_waste_type] -= 1
            counters[selected_waste_type] += 1
            session['waste_type'] = selected_waste_type  # Cập nhật loại rác trong session
        return jsonify({'status': 'success', 'message': 'Counter updated'})
    return jsonify({'status': 'error', 'message': 'Invalid waste type'}), 400

if __name__ == '__main__':
    app.run(debug=True)

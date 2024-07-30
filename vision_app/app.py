from flask import Flask, request, render_template, redirect, url_for, session, jsonify
from PIL import Image
import io, os, requests, json
import google.generativeai as genai
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
    'Linh kiện điện tử': 0
}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif', 'jfif', 'webp'}

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        counters['total_images'] += 1
        file = request.files.get('file')
        url = request.form.get('url')
        webcam_image = request.files.get('webcam_image')
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded_image.jpg')
        
        if file and allowed_file(file.filename):
            file.save(filepath)
        elif url and url.strip():
            Image.open(io.BytesIO(requests.get(url).content)).save(filepath)
        elif webcam_image:
            webcam_image.save(filepath)
        else:
            counters['Không xác định'] += 1
            return render_template('index.html', counters=counters)
        
        result, modified_image_path = detect_labels_and_objects(filepath)
        waste_type = result['waste_type'] or 'Không xác định'
        counters['successful_classifications'] += 1
        counters[waste_type] = counters.get(waste_type, 0) + 1
        
        session.update({
            'objects': result['objects'],
            'waste_type': waste_type,
            'explanation': result.get('explanation', ''),
            'image_url': modified_image_path,
            'initial_waste_type': waste_type
        })
        
        return redirect(url_for('result'))
    
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
    resized_image = image.resize((320, 240))
    resized_image_path = os.path.join(app.config['UPLOAD_FOLDER'], 'modified_uploaded_image.jpg')
    resized_image.save(resized_image_path, 'png')
    prompt_file_path = os.path.join(os.path.dirname(__file__), 'static', 'test', 'tomtat.txt')
    with open(prompt_file_path, "r", encoding="utf-8") as file: prompt= file.read()
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
            session['waste_type'] = selected_waste_type
        return jsonify({'status': 'success', 'message': 'Counter updated'})
    return jsonify({'status': 'error', 'message': 'Invalid waste type'}), 400

@app.route('/settings')
def settings():
    return render_template('settings.html')

@app.route('/report')
def report():
    return render_template('report.html')

if __name__ == '__main__':
    app.run(debug=True)

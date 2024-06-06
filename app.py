from flask import Flask, render_template, request, redirect, url_for, render_template_string
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import requests

app = Flask(__name__)

UPLOAD_FOLDER = '/home/ubuntu/project1/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def calculate_progress(file_size, total_bytes):
    if total_bytes <= 0:
        return 0
    return int((total_bytes / file_size) * 100)

def convert_to_jma_elevation(latitude, longitude):
    elevation_api_url = 'https://cyberjapandata2.gsi.go.jp/general/dem/scripts/getelevation.php'
    params = {
        'lon': longitude,
        'lat': latitude,
        'outtype': 'JSON'
    }
    try:
        response = requests.get(elevation_api_url, params=params)
        response.raise_for_status()
        elevation_data = response.json()
        elevation = elevation_data['elevation']
        return elevation
    except (requests.RequestException, ValueError, KeyError) as e:
        print(f"Failed to get elevation for point ({latitude}, {longitude}): {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)

    uploaded_filename = file.filename
    save_filename = request.form.get('save_filename', uploaded_filename)
    save_filename = save_filename if save_filename.endswith('.gpx') else save_filename + '.gpx'
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], save_filename)
    file.save(save_path)

    gpx_name = request.form.get('gpx_name', 'Default Track Name')
    html_title = request.form.get('html_title', 'HTML Title')

    output_html = process_gpx(save_path, uploaded_filename, gpx_name, html_title)
    return redirect(url_for('progress', filename=output_html))

@app.route('/progress/<path:filename>')  # パス変数を使用してファイルパスを受け取る
def progress(filename):
    # ファイル名からファイルの名前部分を抽出
    filename = os.path.basename(filename)
    return render_template('progress.html', filename=filename)

# progress.html ページでリダイレクトを行うためのルート
@app.route('/redirect_to_generated_file/<path:file_path>')
def redirect_to_generated_file(file_path):
    # 生成された HTML ファイルへのパスを受け取ってリダイレクト
    return redirect(url_for('uploads', filename=file_path), code=302)

def process_gpx(input_gpx, uploaded_filename, gpx_name, html_title):
    # GPX ファイルの解析
    tree = ET.parse(input_gpx)
    root = tree.getroot()

    for elem in root.iter():
        if '}' in elem.tag:
            elem.tag = elem.tag.split('}', 1)[1]

    trk_name_elem = root.find('.//trk/name')
    if trk_name_elem is not None:
        trk_name_elem.text = gpx_name
    else:
        trk = root.find('.//trk')
        if trk is not None:
            new_name_elem = ET.SubElement(trk, 'name')
            new_name_elem.text = gpx_name

    latlngs = []
    gpx_points = []

    for trkpt in root.findall('.//trkpt'):
        lat = float(trkpt.attrib['lat'])
        lon = float(trkpt.attrib['lon'])
        elevation = convert_to_jma_elevation(lat, lon)
        ele = trkpt.find('ele')
        if ele is not None and elevation is not None:
            ele.text = str(elevation)
        latlngs.append({'latitude': lat, 'longitude': lon, 'elevation': elevation})
        gpx_points.append({'latitude': lat, 'longitude': lon, 'elevation': elevation})

    output_filename = input_gpx[:-4] + '_modified.gpx'
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
    tree.write(output_path)

    initial_latitude = latlngs[0]['latitude']
    initial_longitude = latlngs[0]['longitude']

    output_html = input_gpx[:-4] + '_viewer.html'

    with open('templates/gpx_viewer_template.html', 'r') as template_file:
        template_content = template_file.read()
        rendered_html = render_template_string(template_content, html_title=html_title, 
                                                initial_latitude=initial_latitude, initial_longitude=initial_longitude,
                                                gpx_points=gpx_points, output_html=output_html)

    output_html_path = os.path.join(app.config['UPLOAD_FOLDER'], output_html)

    with open(output_html_path, 'w') as html_output_file:
        html_output_file.write(rendered_html)

    return output_html_path  # ファイルパスを返す

if __name__ == '__main__':
    app.run(debug=True)


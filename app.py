import os
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from lxml import etree as ET
import gpxpy

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'

def add_namespace_to_gpx(xml_content):
    try:
        # XMLをパース
        tree = ET.ElementTree(ET.fromstring(xml_content))
        root = tree.getroot()

        # 名前空間が定義されているか確認
        nsmap = root.nsmap
        if 'gpxtpx' not in nsmap:
            nsmap['gpxtpx'] = 'http://www.garmin.com/xmlschemas/TrackPointExtension/v1'
            new_root = ET.Element(root.tag, nsmap=nsmap)
            new_root[:] = root[:]
            xml_content = ET.tostring(new_root, xml_declaration=True, encoding='utf-8')

        # 再パース
        tree = ET.ElementTree(ET.fromstring(xml_content))
        root = tree.getroot()

        return ET.tostring(root, xml_declaration=True, encoding='utf-8')

    except ET.XMLSyntaxError as e:
        print(f"GPXファイルのパース中にエラーが発生しました: {str(e)}")
        return None

def process_gpx(file, save_filename, gpx_name, html_title):
    # ファイルを読み込んで名前空間を追加
    xml_content = file.read()
    xml_content = add_namespace_to_gpx(xml_content)
    if xml_content is None:
        return None, None, None

    try:
        gpx = gpxpy.parse(xml_content)
    except gpxpy.gpx.GPXXMLSyntaxException as e:
        print(f"GPXファイルのパース中にエラーが発生しました: {str(e)}")
        return None, None, None

    # GPXファイル内の<extensions>要素を削除
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                point.extensions = None

    gpx_output_name = f"processed_{save_filename}.gpx"
    output_gpx_path = os.path.join(app.config['UPLOAD_FOLDER'], gpx_output_name)
    with open(output_gpx_path, 'wb') as f:
        f.write(gpx.to_xml().encode('utf-8'))

    gpx_points = [{
        'latitude': point.latitude,
        'longitude': point.longitude,
        'elevation': point.elevation
    } for track in gpx.tracks for segment in track.segments for point in segment.points]

    output_html = f"{gpx_output_name}_viewer.html"
    output_html_path = os.path.join(app.config['UPLOAD_FOLDER'], output_html)
    with open(output_html_path, 'w') as f:
        f.write(render_template('gpx_viewer_template.html', html_title=html_title, initial_latitude=gpx_points[0]['latitude'], initial_longitude=gpx_points[0]['longitude'], gpx_points=gpx_points, output_html=output_html, gpx_output_name=gpx_output_name))
        
    return output_gpx_path, gpx_output_name, gpx_points

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if request.method == 'POST':
        uploaded_file = request.files['file']
        if uploaded_file.filename != '':
            save_filename = request.form['save_filename']
            gpx_name = request.form['gpx_name']
            html_title = request.form['html_title']
            gpx_output_path, gpx_output_name, gpx_points = process_gpx(uploaded_file, save_filename, gpx_name, html_title)
            if gpx_output_path is None:    
                return redirect(url_for('index'))            
            output_html = f"{gpx_output_name}_viewer.html"  # 出力するHTMLファイル名
            output_html_path = os.path.join(app.config['UPLOAD_FOLDER'], output_html)

            # デバッグ出力
            print(f"GPX Output Path: {gpx_output_path}")
            print(f"HTML Output Path: {output_html_path}")
            
            with open(output_html_path, 'w') as f:
                f.write(render_template('gpx_viewer_template.html', html_title=html_title, initial_latitude=gpx_points[0]['latitude'], initial_longitude=gpx_points[0]['longitude'], gpx_points=gpx_points, output_html=output_html, gpx_output_name=gpx_output_name))

            # ファイルの存在確認
            print(f"GPXファイル存在: {os.path.exists(gpx_output_path)}")
            print(f"HTMLファイル存在: {os.path.exists(output_html_path)}")
            
            return redirect(url_for('processing_completed', gpx_output_name=gpx_output_name))
    return redirect(url_for('index'))

@app.route('/processing_completed/<gpx_output_name>')
def processing_completed(gpx_output_name):
    html_file_name = f"{gpx_output_name}_viewer.html"
    return render_template('progress.html', gpx_output_name=gpx_output_name, html_file_name=html_file_name)

# ファイルを提供するためのルートを設定
@app.route('/uploads/<path:filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)

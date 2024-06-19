import os
import gpxpy
import gpxpy.gpx
import requests
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'

def get_elevation(latitude, longitude):
    url = f'https://cyberjapandata2.gsi.go.jp/general/dem/scripts/getelevation.php?lon={longitude}&lat={latitude}'
    response = requests.get(url)
    if response.status_code == 200:
        try:
            elevation_data = response.json()
            if 'elevation' in elevation_data:
                return elevation_data['elevation']
        except ValueError:
            print(f"Error parsing JSON response for ({latitude}, {longitude}): {response.text}")
    else:
        print(f"Error fetching elevation data for ({latitude}, {longitude}): HTTP {response.status_code}")
    return None

def process_gpx(file, save_filename, gpx_name, html_title):
    gpx = gpxpy.parse(file)

    # GPXファイルの処理
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                # 各座標の標高を取得し、GPXファイルの標高情報を書き換える
                elevation = get_elevation(point.latitude, point.longitude)
                if elevation is not None:
                    print(f"Setting elevation for ({point.latitude}, {point.longitude}) to {elevation}")
                    point.elevation = elevation
                else:	
                    print(f"Failed to get elevation for point ({point.latitude}, {point.longitude})")

    # GPXファイル内の<extensions>要素を削除
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                point.extensions = None

    gpx_output_name = f"processed_{save_filename}.gpx"
    output_gpx_path = os.path.join(app.config['UPLOAD_FOLDER'], gpx_output_name)
    with open(output_gpx_path, 'w') as f:
        f.write(gpx.to_xml())

    gpx_points = [{
        'latitude': point.latitude,
        'longitude': point.longitude,
        'elevation': point.elevation
    } for track in gpx.tracks for segment in track.segments for point in segment.points]

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
            output_html = f"{gpx_output_name}_viewer.html"  # 出力するHTMLファイル名
            output_html_path = os.path.join(app.config['UPLOAD_FOLDER'], output_html)
            with open(output_html_path, 'w') as f:
                f.write(render_template('gpx_viewer_template.html', html_title=html_title, initial_latitude=gpx_points[0]['latitude'], initial_longitude=gpx_points[0]['longitude'], gpx_points=gpx_points, output_html=output_html))
            return redirect(url_for('processing_completed', gpx_output_name=output_html))
    return redirect(url_for('index'))

@app.route('/processing_completed/<gpx_output_name>')
def processing_completed(gpx_output_name):
    return render_template('progress.html', filename=gpx_output_name)

@app.route('/redirect_to_generated_file/<path:filename>')
def redirect_to_generated_file(filename):
    return redirect(url_for('static', filename=os.path.join('uploads', filename)))

if __name__ == '__main__':
    app.run(debug=True)

from flask import Flask, render_template, request
import os
import gpxpy
import gpxpy.gpx
import plotly.graph_objs as go
import pandas as pd
import requests
from geopy.distance import geodesic

app = Flask(__name__)
UPLOAD_FOLDER = '/home/ubuntu/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return 'No file part'
        
        file = request.files['file']
        
        if file.filename == '':
            return 'No selected file'
        
        if file:
            filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filename)

            # HTMLファイル名を生成
            output_html = os.path.join(app.config['UPLOAD_FOLDER'], file.filename[:-4] + '_gpx_viewer.html')

            # GPXファイルの処理
            process_gpx(filename, output_html)

            return f'File {file.filename} uploaded successfully.'

    return render_template('upload_form.html')

def process_gpx(input_gpx, output_html):
    # GPXファイルの読み込み
    with open(input_gpx, 'r') as gpx_file:
        gpx = gpxpy.parse(gpx_file)

    # 国土地理院の標高APIのURL
    elevation_api_url = 'https://cyberjapandata2.gsi.go.jp/general/dem/scripts/getelevation.php'

    # トラックポイントの抽出と標高データの取得
    track_points = []
    distance = 0
    prev_point = None

    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                params = {
                    'lon': point.longitude,
                    'lat': point.latitude,
                    'outtype': 'JSON'
                }
                try:
                    response = requests.get(elevation_api_url, params=params)
                    response.raise_for_status()
                    elevation_data = response.json()
                    elevation = elevation_data['elevation']
                except (requests.RequestException, ValueError, KeyError) as e:
                    print(f"Failed to get elevation for point ({point.latitude}, {point.longitude}): {e}")
                    elevation = point.elevation  # Fallback to original elevation

                if prev_point is not None:
                    distance += geodesic((prev_point.latitude, prev_point.longitude),
                                         (point.latitude, point.longitude)).kilometers
                track_points.append([point.latitude, point.longitude, elevation, distance, point.time.time()])
                prev_point = point

    # データフレームに変換
    df = pd.DataFrame(track_points, columns=['lat', 'lon', 'ele', 'distance_km', 'time'])

    # 標高グラフの作成
    fig = go.Figure(go.Scatter(x=df['distance_km'], y=df['ele'], mode='lines'))
    fig.update_layout(
        title='標高グラフ',
        xaxis_title='距離 (km)',
        yaxis_title='標高 (m)'
    )

    # HTMLファイルに保存
    fig.write_html(output_html)

if __name__ == '__main__':
    app.run(debug=True)

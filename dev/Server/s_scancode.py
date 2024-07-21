import traceback

import pytz
from flask import Flask, request, jsonify
import pymysql
import configparser

app = Flask(__name__)

# 加载配置文件
def load_config():
    config = configparser.ConfigParser()
    config.read('server_config.ini')
    return config

config = load_config()

# 连接到数据库
def get_db_connection():
    return pymysql.connect(
        host=config.get('database', 'host'),
        user=config.get('database', 'user'),
        password=config.get('database', 'password'),
        database=config.get('database', 'database'),
        ssl={'ssl': {
            'ca': config.get('database', 'ssl_ca'),
        }}
    )

# 检查API密钥
def check_api_key(request):
    api_key = request.headers.get('X-API-KEY')
    return api_key == config.get('api', 'key')

@app.route('/upload', methods=['POST'])
def upload_data():
    data = request.json
    # 输出收到的数据
    app.logger.info(f"Received data: {data}")

    if not check_api_key(request):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    if not isinstance(data, list):
        return jsonify({"error": "Invalid data format"}), 400

    connection = get_db_connection()
    cursor = connection.cursor()

    success_ids = []
    failed_records = []

    try:
        for item in data:
            record_id = item.get('id')
            barcode = item.get('barcode')
            # 时区为UTC 8时区
            timestamp = item.get('timestamp')


            # timestamp = item.get('timestamp')
            site_id = item.get('site_id')
            if record_id and barcode and timestamp:
                try:
                    cursor.execute("INSERT INTO scancode ( uuid,time, barcode, site) VALUES (%s, %s, %s, %s)",
                                   (record_id, timestamp, barcode, site_id))
                    success_ids.append(record_id)
                except Exception as e:
                    failed_records.append({
                        'id': record_id,
                        'error': str(e)
                    })
        connection.commit()
    except Exception as e:
        connection.rollback()
        app.logger.error(f"Error occurred: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500
    finally:
        connection.close()

    return jsonify({
        "status": "partial success" if failed_records else "success",
        "success_ids": success_ids,
        "failed_records": failed_records
    }), 200

# 用code字段查询数据库中的数据
@app.route('/search/<code>', methods=['GET'])
def search_data(code):
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM scancode WHERE barcode = %s", code)
    data = cursor.fetchall()

    connection.close()

    return jsonify(data)


if __name__ == '__main__':
    #要在控制台看到客户端提交的数据，需要将日志级别设置为DEBUG
    app.logger.setLevel('DEBUG')

    app.run(debug=True, port=5000)
